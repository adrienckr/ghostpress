"""Tests for ``ghostpress.build`` (sniff -> codegen orchestrator)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ghostpress._types import BuildOptions, SniffResult
from ghostpress.build import build


def _make_fake_sniff(
    *,
    manifest_name: str = "api-example-com",
    source_url: str = "https://api.example.com",
):
    """Build a coroutine that writes manifest.json + har.json into the per-CLI dir."""

    async def _fake(options):
        out_dir = Path(options.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = out_dir / "manifest.json"
        har_path = out_dir / "har.json"
        manifest_payload = {
            "schema_version": 1,
            "name": manifest_name,
            "source_url": source_url,
            "capture_time": "2026-05-09T12:00:00Z",
            "user_agent": "ghostpress-test/0.1",
            "endpoints": [
                {
                    "method": "GET",
                    "url_template": f"{source_url}/v1/products",
                    "response_content_type": "application/json",
                    "request_count": 1,
                    "sample": {
                        "status": 200,
                        "request_headers": {"accept": "application/json"},
                        "request_body_preview": None,
                        "response_headers": {"content-type": "application/json"},
                        "response_body_preview": "{\"items\":[]}",
                        "response_size_bytes": 11,
                    },
                }
            ],
            "notes": None,
        }
        manifest_path.write_text(json.dumps(manifest_payload))
        har_path.write_text(json.dumps({"log": {"version": "1.2", "entries": []}}))
        return SniffResult(
            har_path=str(har_path),
            manifest_path=str(manifest_path),
            endpoint_count=1,
            captcha_detected=False,
        )

    return _fake


async def test_build_creates_per_cli_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())
    options = BuildOptions(
        url="https://api.example.com",
        out_dir=str(tmp_path),
        formats=["python_cli"],
    )
    result = await build(options)
    assert Path(result.out_dir).is_dir()


async def test_build_writes_cli_py(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())
    options = BuildOptions(
        url="https://api.example.com",
        out_dir=str(tmp_path),
        formats=["python_cli"],
    )
    result = await build(options)
    assert (Path(result.out_dir) / "cli.py").exists()


async def test_build_writes_pyproject_toml(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())
    options = BuildOptions(
        url="https://api.example.com",
        out_dir=str(tmp_path),
        formats=["python_cli"],
    )
    result = await build(options)
    assert (Path(result.out_dir) / "pyproject.toml").exists()


async def test_build_result_lists_artifacts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())
    options = BuildOptions(
        url="https://api.example.com",
        out_dir=str(tmp_path),
        formats=["python_cli"],
    )
    result = await build(options)
    assert "cli.py" in result.artifacts


async def test_build_result_command_count_populated(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())
    options = BuildOptions(
        url="https://api.example.com",
        out_dir=str(tmp_path),
        formats=["python_cli"],
    )
    result = await build(options)
    assert result.command_count == 1


async def test_build_name_derived_from_url_host(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())
    options = BuildOptions(
        url="https://api.example.com/path",
        out_dir=str(tmp_path),
        formats=["python_cli"],
    )
    result = await build(options)
    assert Path(result.out_dir).name == "api-example-com"


async def test_build_explicit_name_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())
    options = BuildOptions(
        url="https://api.example.com",
        out_dir=str(tmp_path),
        name="my-cli",
        formats=["python_cli"],
    )
    result = await build(options)
    assert Path(result.out_dir).name == "my-cli"


async def test_build_codegen_error_is_wrapped(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("ghostpress.sniff.sniff", _make_fake_sniff())

    def _boom(spec, formats):
        raise ValueError("boom")

    monkeypatch.setattr("ghostpress.codegen.generate_all", _boom)

    options = BuildOptions(
        url="https://api.example.com",
        out_dir=str(tmp_path),
        formats=["python_cli"],
    )
    with pytest.raises(RuntimeError, match="codegen failed"):
        await build(options)
