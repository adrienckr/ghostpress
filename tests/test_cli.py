"""Tests for ``ghostpress.cli`` (typer surface)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from ghostpress._types import (
    NavigateResult,
    SessionCloseResult,
    SessionOpenResult,
    SniffResult,
)
from ghostpress.cli import app

runner = CliRunner()


def test_top_level_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout + result.output
    assert "sniff" in out
    assert "mcp" in out
    assert "run" in out


def test_sniff_help_exits_zero():
    result = runner.invoke(app, ["sniff", "--help"])
    assert result.exit_code == 0


def test_run_help_exits_zero():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0


def test_mcp_help_exits_zero():
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0


def test_sniff_command_runs_with_stub(monkeypatch, tmp_path: Path):
    out_dir = tmp_path / "capture"
    har_path = out_dir / "har.json"
    manifest_path = out_dir / "manifest.json"

    async def fake_sniff(_options):
        return SniffResult(
            har_path=str(har_path),
            manifest_path=str(manifest_path),
            endpoint_count=3,
            captcha_detected=False,
        )

    monkeypatch.setattr("ghostpress.sniff.sniff", fake_sniff)

    result = runner.invoke(
        app,
        [
            "sniff",
            "https://example.com/",
            "--out",
            str(out_dir),
            "--duration",
            "1.0",
        ],
    )
    assert result.exit_code == 0


def test_sniff_command_failure_exits_one(monkeypatch, tmp_path: Path):
    async def fake_sniff(_options):
        raise RuntimeError("camoufox launch failed: boom")

    monkeypatch.setattr("ghostpress.sniff.sniff", fake_sniff)

    result = runner.invoke(
        app,
        [
            "sniff",
            "https://example.com/",
            "--out",
            str(tmp_path / "out"),
            "--duration",
            "1.0",
        ],
    )
    assert result.exit_code == 1


def test_run_command_executes_flow(monkeypatch, tmp_path: Path):
    flow_yaml = tmp_path / "flow.yaml"
    flow_yaml.write_text(
        """
name: smoke
description: tiny demo flow
steps:
  - action: navigate
    args:
      url: https://example.com/
  - action: read_page
""".strip()
    )

    async def fake_open(_registry, profile=None, proxy=None):
        return SessionOpenResult(session_id="sess-1")

    async def fake_close(_registry, session_id):
        return SessionCloseResult(session_id=session_id)

    async def fake_navigate(_registry, *, session_id, url, wait_for=None,
                            timeout_ms=30000):
        return NavigateResult(
            final_url=url, status=200, title="ok"
        )

    from ghostpress._types import ReadPageResult

    async def fake_read_page(_registry, *, session_id):
        return ReadPageResult(title="ok", url="https://example.com/", markdown="hi")

    monkeypatch.setattr("ghostpress.tools.stealth_session_open", fake_open)
    monkeypatch.setattr("ghostpress.tools.stealth_session_close", fake_close)
    monkeypatch.setattr("ghostpress.tools.stealth_navigate", fake_navigate)
    monkeypatch.setattr("ghostpress.tools.stealth_read_page", fake_read_page)

    out_dir = tmp_path / "runs-out"
    result = runner.invoke(
        app, ["run", str(flow_yaml), "--out", str(out_dir)]
    )
    assert result.exit_code == 0


def test_run_command_session_open_failure_exits_one(monkeypatch, tmp_path: Path):
    flow_yaml = tmp_path / "flow.yaml"
    flow_yaml.write_text(
        """
name: smoke
steps:
  - action: navigate
    args:
      url: https://example.com/
""".strip()
    )

    async def fake_open(_registry, profile=None, proxy=None):
        return SessionOpenResult(ok=False, error="cannot open")

    async def fake_close(_registry, session_id):
        return SessionCloseResult(session_id=session_id)

    monkeypatch.setattr("ghostpress.tools.stealth_session_open", fake_open)
    monkeypatch.setattr("ghostpress.tools.stealth_session_close", fake_close)

    out_dir = tmp_path / "runs-out"
    result = runner.invoke(
        app, ["run", str(flow_yaml), "--out", str(out_dir)]
    )
    assert result.exit_code == 1
