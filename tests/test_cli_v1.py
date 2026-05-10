"""Tests for the v1.0 ``build`` and ``gallery`` Typer commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ghostpress._types import BuildResult
from ghostpress.cli import app

runner = CliRunner()


def test_build_help_exits_zero() -> None:
    result = runner.invoke(app, ["build", "--help"])
    assert result.exit_code == 0


def test_gallery_help_exits_zero() -> None:
    result = runner.invoke(app, ["gallery", "--help"])
    assert result.exit_code == 0


def test_build_without_url_or_prompt_exits_one() -> None:
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 1


def test_build_without_url_or_prompt_emits_error_message() -> None:
    result = runner.invoke(app, ["build"])
    combined = result.stdout + result.output + (result.stderr or "")
    assert "must provide URL or --prompt" in combined


def test_build_with_url_invokes_build(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    async def _fake_build(options):
        captured["url"] = options.url
        return BuildResult(
            out_dir=str(tmp_path / "x"),
            har_path=str(tmp_path / "x" / "har.json"),
            manifest_path=str(tmp_path / "x" / "manifest.json"),
            artifacts=["cli.py"],
            command_count=1,
            captcha_detected=False,
            elapsed_seconds=0.5,
        )

    monkeypatch.setattr("ghostpress.build.build", _fake_build)

    result = runner.invoke(
        app,
        ["build", "https://x", "--out", str(tmp_path), "--formats", "python_cli"],
    )
    assert result.exit_code == 0


def test_build_success_prints_built_marker(monkeypatch, tmp_path: Path) -> None:
    async def _fake_build(_options):
        return BuildResult(
            out_dir=str(tmp_path / "x"),
            har_path=str(tmp_path / "x" / "har.json"),
            manifest_path=str(tmp_path / "x" / "manifest.json"),
            artifacts=["cli.py"],
            command_count=2,
            captcha_detected=False,
            elapsed_seconds=0.5,
        )

    monkeypatch.setattr("ghostpress.build.build", _fake_build)

    result = runner.invoke(
        app,
        ["build", "https://x", "--out", str(tmp_path), "--formats", "python_cli"],
    )
    combined = result.stdout + result.output + (result.stderr or "")
    assert "built" in combined


def test_build_runtime_error_exits_one(monkeypatch, tmp_path: Path) -> None:
    async def _boom(_options):
        raise RuntimeError("codegen failed: bad thing")

    monkeypatch.setattr("ghostpress.build.build", _boom)

    result = runner.invoke(
        app,
        ["build", "https://x", "--out", str(tmp_path), "--formats", "python_cli"],
    )
    assert result.exit_code == 1


def test_gallery_runs_without_error() -> None:
    result = runner.invoke(app, ["gallery"])
    assert result.exit_code == 0
