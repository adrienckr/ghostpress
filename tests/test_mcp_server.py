"""Tests for ``ghostpress.mcp_server`` (tool defs + server build)."""

from __future__ import annotations

import pytest


def test_tool_defs_count():
    from ghostpress.mcp_server import _TOOL_DEFS

    assert len(_TOOL_DEFS) == 9


def test_tool_defs_names():
    from ghostpress.mcp_server import _TOOL_DEFS

    names = {t["name"] for t in _TOOL_DEFS}
    expected = {
        "stealth_session_open",
        "stealth_session_close",
        "stealth_navigate",
        "stealth_click",
        "stealth_fill",
        "stealth_read_page",
        "stealth_screenshot",
        "stealth_capture_har",
        "stealth_export_manifest",
    }
    assert names == expected


def test_tool_defs_have_descriptions():
    from ghostpress.mcp_server import _TOOL_DEFS

    for tool in _TOOL_DEFS:
        assert tool.get("description"), f"missing description: {tool['name']}"


def test_tool_defs_have_input_schema_objects():
    from ghostpress.mcp_server import _TOOL_DEFS

    for tool in _TOOL_DEFS:
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert "properties" in schema


@pytest.mark.parametrize(
    "name,required",
    [
        ("stealth_session_close", ["session_id"]),
        ("stealth_navigate", ["session_id", "url"]),
        ("stealth_click", ["session_id", "selector"]),
        ("stealth_fill", ["session_id", "selector", "text"]),
        ("stealth_read_page", ["session_id"]),
        ("stealth_screenshot", ["session_id"]),
        ("stealth_capture_har", ["session_id", "duration_seconds"]),
        ("stealth_export_manifest", ["name", "source_url", "har_json"]),
    ],
)
def test_tool_required_fields(name: str, required: list[str]):
    from ghostpress.mcp_server import _TOOL_DEFS

    spec = next(t for t in _TOOL_DEFS if t["name"] == name)
    assert spec["inputSchema"].get("required") == required


def test_build_server_returns_server():
    try:
        from ghostpress.mcp_server import build_server
    except ImportError:
        pytest.skip("MCP SDK not available")

    try:
        server = build_server()
    except ImportError:
        pytest.skip("MCP SDK not available at build time")

    # Sanity: registry was attached.
    assert getattr(server, "_ghostpress_registry", None) is not None
