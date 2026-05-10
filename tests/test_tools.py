"""Tests for ``ghostpress.tools`` (SessionRegistry + tool functions)."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock

import pytest

from ghostpress._types import HAR
from ghostpress.tools import (
    SessionRegistry,
    stealth_click,
    stealth_export_manifest,
    stealth_fill,
    stealth_navigate,
    stealth_read_page,
    stealth_screenshot,
    stealth_session_close,
    stealth_session_open,
)


async def test_registry_open_returns_session_id(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    assert isinstance(sid, str)
    assert len(sid) > 0


async def test_registry_get_returns_entry(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    entry = registry.get(sid)
    assert "page" in entry
    assert "browser" in entry


async def test_registry_close_removes_entry(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    await registry.close(sid)
    with pytest.raises(KeyError):
        registry.get(sid)


async def test_registry_close_unknown_raises(fake_camoufox):
    registry = SessionRegistry()
    with pytest.raises(KeyError):
        await registry.close("nope")


async def test_registry_aclose_clears_all(fake_camoufox):
    registry = SessionRegistry()
    s1 = await registry.open()
    s2 = await registry.open()
    await registry.aclose()
    with pytest.raises(KeyError):
        registry.get(s1)
    with pytest.raises(KeyError):
        registry.get(s2)


async def test_session_open_tool_ok(fake_camoufox):
    registry = SessionRegistry()
    result = await stealth_session_open(registry)
    assert result.ok is True
    assert result.session_id != ""


async def test_session_close_tool_ok(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    result = await stealth_session_close(registry, session_id=sid)
    assert result.ok is True


async def test_session_close_tool_unknown(fake_camoufox):
    registry = SessionRegistry()
    result = await stealth_session_close(registry, session_id="missing")
    assert result.ok is False
    assert result.error is not None


async def test_navigate_returns_final_url_and_title(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    result = await stealth_navigate(
        registry, session_id=sid, url="https://target.example/"
    )
    assert result.ok is True
    assert result.final_url == "https://target.example/"
    assert result.title == "Example"
    assert result.status == 200


async def test_navigate_records_goto_call(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    await stealth_navigate(registry, session_id=sid, url="https://target.example/")
    page = registry.get(sid)["page"]
    assert page.goto_calls[0][0] == "https://target.example/"


async def test_navigate_error_path(fake_camoufox, monkeypatch):
    registry = SessionRegistry()
    sid = await registry.open()
    page = registry.get(sid)["page"]
    page.goto = AsyncMock(side_effect=RuntimeError("boom"))
    result = await stealth_navigate(registry, session_id=sid, url="https://x/")
    assert result.ok is False
    assert "boom" in (result.error or "")


async def test_click_invokes_locator_click(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    result = await stealth_click(registry, session_id=sid, selector="#go")
    assert result.ok is True
    assert result.selector == "#go"
    page = registry.get(sid)["page"]
    assert "#go" in page.locator_calls


async def test_fill_invokes_locator_fill(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    result = await stealth_fill(
        registry, session_id=sid, selector="#name", text="alice"
    )
    assert result.ok is True
    assert result.selector == "#name"


async def test_read_page_returns_markdown(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    result = await stealth_read_page(registry, session_id=sid)
    assert result.ok is True
    assert result.title == "Example"
    assert result.markdown == "hi there"


async def test_read_page_falls_back_to_content_on_inner_text_error(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    page = registry.get(sid)["page"]
    page.inner_text = AsyncMock(side_effect=RuntimeError("nope"))
    result = await stealth_read_page(registry, session_id=sid)
    assert result.ok is True
    # The fake content_html contains "hi" inside body tags; tags are stripped.
    assert "hi" in result.markdown


async def test_screenshot_returns_base64(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    result = await stealth_screenshot(registry, session_id=sid)
    assert result.ok is True
    decoded = base64.b64decode(result.png_base64)
    assert decoded == b"PNGDATA"


async def test_screenshot_includes_viewport_size(fake_camoufox):
    registry = SessionRegistry()
    sid = await registry.open()
    result = await stealth_screenshot(registry, session_id=sid)
    assert result.width == 1280
    assert result.height == 720


async def test_export_manifest_pure(sample_har: HAR):
    result = await stealth_export_manifest(
        sample_har, name="t", source_url="https://api.example.com"
    )
    assert result.ok is True
    assert result.manifest is not None
    assert result.manifest.schema_version == 1
    assert result.manifest.name == "t"
    assert len(result.manifest.endpoints) == 4


async def test_navigate_unknown_session_returns_error(fake_camoufox):
    registry = SessionRegistry()
    result = await stealth_navigate(
        registry, session_id="nope", url="https://x/"
    )
    assert result.ok is False
    assert result.error is not None
