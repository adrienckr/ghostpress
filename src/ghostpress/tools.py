"""Stealth-browser action surface.

Each tool returns a typed :class:`ghostpress._types.ToolResult` subclass.
Errors are surfaced via the ``ok=False`` / ``error=...`` envelope rather than
raising, because the MCP server marshals these directly to the client.

A :class:`SessionRegistry` tracks per-session camoufox + Playwright handles so
multi-step flows survive across MCP tool calls.
"""

from __future__ import annotations

import asyncio
import base64
import re
import secrets
from datetime import UTC, datetime
from typing import Any

from camoufox.async_api import AsyncCamoufox

from ghostpress._types import (
    HAR,
    BrowserProfile,
    CaptureHarResult,
    ClickResult,
    ExportManifestResult,
    FillResult,
    NavigateResult,
    ProxyConfig,
    ReadPageResult,
    ScreenshotResult,
    SessionCloseResult,
    SessionOpenResult,
)
from ghostpress.fingerprint import profile_to_camoufox_kwargs
from ghostpress.manifest import har_to_manifest
from ghostpress.proxy import proxy_to_playwright_dict
from ghostpress.sniff import build_har_from_events

__all__ = [
    "SessionRegistry",
    "stealth_capture_har",
    "stealth_click",
    "stealth_export_manifest",
    "stealth_fill",
    "stealth_navigate",
    "stealth_read_page",
    "stealth_screenshot",
    "stealth_session_close",
    "stealth_session_open",
]


_READ_PAGE_LIMIT = 16000
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class SessionRegistry:
    """Tracks live camoufox sessions by id.

    The registry is process-local; an MCP server keeps a single instance and
    threads it through every tool call. Sessions are auto-evicted on
    ``stealth_session_close`` or when the registry's ``aclose()`` is called.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    async def open(
        self,
        profile: BrowserProfile | None = None,
        proxy: ProxyConfig | None = None,
    ) -> str:
        """Launch a camoufox session and return its id."""

        profile = profile or BrowserProfile()
        kwargs = profile_to_camoufox_kwargs(profile)
        if proxy is not None:
            kwargs["proxy"] = proxy_to_playwright_dict(proxy)

        cm = AsyncCamoufox(**kwargs)
        browser = await cm.__aenter__()
        page = await browser.new_page()

        session_id = secrets.token_urlsafe(8)
        self._sessions[session_id] = {
            "context_manager": cm,
            "browser": browser,
            "page": page,
        }
        return session_id

    async def close(self, session_id: str) -> None:
        """Close and evict a session."""

        if session_id not in self._sessions:
            raise KeyError(session_id)
        entry = self._sessions[session_id]
        cm = entry["context_manager"]
        try:
            await cm.__aexit__(None, None, None)
        finally:
            self._sessions.pop(session_id, None)

    async def aclose(self) -> None:
        """Close all sessions."""

        for sid in list(self._sessions.keys()):
            try:
                await self.close(sid)
            except Exception:
                # Best-effort cleanup; keep going.
                continue

    def get(self, session_id: str) -> dict[str, Any]:
        """Retrieve the underlying handle (camoufox+page). Internal use."""

        if session_id not in self._sessions:
            raise KeyError(session_id)
        return self._sessions[session_id]


# ---------------------------------------------------------------------------
# Tool implementations.
#
# Each tool accepts a SessionRegistry and a session_id (created via
# stealth_session_open). The registry owns the lifecycle.
# ---------------------------------------------------------------------------


async def stealth_session_open(
    registry: SessionRegistry,
    profile: BrowserProfile | None = None,
    proxy: ProxyConfig | None = None,
) -> SessionOpenResult:
    """Open a stealth session. Returns a session_id usable for subsequent calls."""

    try:
        session_id = await registry.open(profile=profile, proxy=proxy)
        return SessionOpenResult(session_id=session_id)
    except Exception as e:
        return SessionOpenResult(ok=False, error=str(e))


async def stealth_session_close(
    registry: SessionRegistry,
    session_id: str,
) -> SessionCloseResult:
    """Close a stealth session."""

    try:
        await registry.close(session_id)
        return SessionCloseResult(session_id=session_id)
    except Exception as e:
        return SessionCloseResult(ok=False, error=str(e), session_id=session_id)


async def stealth_navigate(
    registry: SessionRegistry,
    session_id: str,
    url: str,
    *,
    wait_for: str | None = None,
    timeout_ms: int = 30_000,
) -> NavigateResult:
    """Navigate to ``url``; optionally wait for a CSS selector before returning."""

    try:
        page = registry.get(session_id)["page"]
        response = await page.goto(
            url, wait_until="domcontentloaded", timeout=timeout_ms
        )
        if wait_for:
            await page.locator(wait_for).wait_for(timeout=timeout_ms)
        status = response.status if response is not None else 0
        title = await page.title()
        return NavigateResult(
            final_url=page.url,
            status=status,
            title=title,
        )
    except Exception as e:
        return NavigateResult(ok=False, error=str(e))


async def stealth_click(
    registry: SessionRegistry,
    session_id: str,
    selector: str,
    *,
    timeout_ms: int = 10_000,
) -> ClickResult:
    """Click the first element matching ``selector``."""

    try:
        page = registry.get(session_id)["page"]
        await page.locator(selector).click(timeout=timeout_ms)
        return ClickResult(selector=selector)
    except Exception as e:
        return ClickResult(ok=False, error=str(e), selector=selector)


async def stealth_fill(
    registry: SessionRegistry,
    session_id: str,
    selector: str,
    text: str,
    *,
    timeout_ms: int = 10_000,
) -> FillResult:
    """Fill an input matching ``selector`` with ``text``."""

    try:
        page = registry.get(session_id)["page"]
        await page.locator(selector).fill(text, timeout=timeout_ms)
        return FillResult(selector=selector)
    except Exception as e:
        return FillResult(ok=False, error=str(e), selector=selector)


async def stealth_read_page(
    registry: SessionRegistry,
    session_id: str,
) -> ReadPageResult:
    """Return the current page as a markdown digest (title + readable content)."""

    try:
        page = registry.get(session_id)["page"]
        title = await page.title()
        url = page.url

        try:
            text = await page.inner_text("body")
        except Exception:
            html = await page.content()
            stripped = _SCRIPT_STYLE_RE.sub("", html)
            text = _TAG_RE.sub(" ", stripped)

        markdown = _WS_RE.sub(" ", text).strip()
        if len(markdown) > _READ_PAGE_LIMIT:
            markdown = markdown[:_READ_PAGE_LIMIT]

        return ReadPageResult(title=title, url=url, markdown=markdown)
    except Exception as e:
        return ReadPageResult(ok=False, error=str(e))


async def stealth_screenshot(
    registry: SessionRegistry,
    session_id: str,
    *,
    full_page: bool = False,
) -> ScreenshotResult:
    """Capture a PNG screenshot, base64-encoded for transport."""

    try:
        page = registry.get(session_id)["page"]
        png_bytes = await page.screenshot(full_page=full_page)
        encoded = base64.b64encode(png_bytes).decode("ascii")

        viewport = page.viewport_size or {}
        width = int(viewport.get("width", 0)) if isinstance(viewport, dict) else 0
        height = int(viewport.get("height", 0)) if isinstance(viewport, dict) else 0

        return ScreenshotResult(
            png_base64=encoded,
            width=width,
            height=height,
        )
    except Exception as e:
        return ScreenshotResult(ok=False, error=str(e))


async def stealth_capture_har(
    registry: SessionRegistry,
    session_id: str,
    duration_seconds: float,
) -> CaptureHarResult:
    """Capture network events for ``duration_seconds`` and return a HAR."""

    try:
        page = registry.get(session_id)["page"]
        events: list[dict] = []

        def _on_request(request) -> None:
            events.append(
                {
                    "kind": "request",
                    "time": datetime.now(UTC).isoformat(),
                    "request_id": id(request),
                    "method": request.method,
                    "url": request.url,
                    "headers": dict(request.headers),
                    "post_data": request.post_data,
                }
            )

        async def _on_response(response) -> None:
            try:
                body = await response.body()
                body_size = len(body) if body else 0
            except Exception:
                body_size = 0
            events.append(
                {
                    "kind": "response",
                    "time": datetime.now(UTC).isoformat(),
                    "request_id": id(response.request),
                    "method": response.request.method,
                    "url": response.url,
                    "status": response.status,
                    "response_headers": dict(response.headers),
                    "mime_type": response.headers.get("content-type", ""),
                    "body_size": body_size,
                }
            )

        def _on_failed(request) -> None:
            events.append(
                {
                    "kind": "failed",
                    "time": datetime.now(UTC).isoformat(),
                    "request_id": id(request),
                    "method": request.method,
                    "url": request.url,
                    "headers": dict(request.headers),
                }
            )

        def _response_handler(response) -> None:
            asyncio.create_task(_on_response(response))

        page.on("request", _on_request)
        page.on("response", _response_handler)
        page.on("requestfailed", _on_failed)

        try:
            await asyncio.sleep(duration_seconds)
        finally:
            page.remove_listener("request", _on_request)
            page.remove_listener("response", _response_handler)
            page.remove_listener("requestfailed", _on_failed)

        har = build_har_from_events(events)
        return CaptureHarResult(
            har=har,
            duration_seconds=duration_seconds,
            captcha_detected=False,
        )
    except Exception as e:
        return CaptureHarResult(
            ok=False,
            error=str(e),
            duration_seconds=duration_seconds,
        )


async def stealth_export_manifest(
    har: HAR,
    *,
    name: str,
    source_url: str,
) -> ExportManifestResult:
    """Convert a HAR to a printing-press manifest. Pure function (no session)."""

    try:
        capture_time = datetime.now(UTC).isoformat()
        manifest = har_to_manifest(
            har,
            name=name,
            source_url=source_url,
            capture_time=capture_time,
        )
        return ExportManifestResult(manifest=manifest)
    except Exception as e:
        return ExportManifestResult(ok=False, error=str(e))
