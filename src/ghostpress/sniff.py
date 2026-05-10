"""Stealth navigation + HAR capture.

Public surface:

- :func:`sniff` — async one-shot: launch camoufox, navigate, capture HAR for a
  configurable window, write artifacts to disk, return :class:`SniffResult`.

This module wires camoufox + Playwright network events into a HAR document.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from camoufox.async_api import AsyncCamoufox

from ghostpress._types import (
    HAR,
    HAREntry,
    HARLog,
    HARRequest,
    HARResponse,
    SniffOptions,
    SniffResult,
)
from ghostpress.fingerprint import profile_to_camoufox_kwargs
from ghostpress.manifest import har_to_manifest
from ghostpress.proxy import proxy_to_playwright_dict

__all__ = ["build_har_from_events", "sniff"]


_CAPTCHA_SELECTOR = (
    "iframe[src*='hcaptcha'], "
    "iframe[src*='recaptcha'], "
    "iframe[src*='turnstile'], "
    "div[id*='cf-challenge'], "
    "div[class*='captcha']"
)


def _headers_to_har(headers: dict[str, str]) -> list[dict[str, str]]:
    return [{"name": k, "value": v} for k, v in headers.items()]


def _detect_captcha_signal(html_or_url: str) -> str | None:
    lowered = html_or_url.lower()
    if "hcaptcha" in lowered:
        return "hcaptcha"
    if "recaptcha" in lowered:
        return "recaptcha"
    if "turnstile" in lowered:
        return "turnstile"
    if "cf-challenge" in lowered or "cloudflare" in lowered:
        return "cloudflare"
    return None


async def sniff(options: SniffOptions) -> SniffResult:
    """Run a sniff session and return the result.

    Implementation responsibilities (see :class:`SniffOptions`):

    1. Resolve ``out_dir`` (create if missing) and pick artifact paths
       ``har.json`` and ``manifest.json`` inside it.
    2. Launch ``AsyncCamoufox`` with the requested profile + proxy.
    3. Subscribe to ``page.on("request" | "response" | "requestfinished" |
       "requestfailed")`` and accumulate :class:`HAREntry` rows.
    4. Navigate to ``options.url`` and idle for ``options.duration_seconds``
       (or until ``options.interact`` is False and the page is quiet).
    5. Detect common captcha walls (selectors / titles) and set the captcha
       fields on the result. Do not solve.
    6. Convert events → :class:`HAR` and persist to ``har.json``.
    7. Convert HAR → :class:`Manifest` via :func:`ghostpress.manifest.har_to_manifest`
       and persist to ``manifest.json``.
    8. Return :class:`SniffResult` populated with paths + counts.

    Raises :class:`RuntimeError` for camoufox launch failures, with the
    underlying error wrapped.
    """

    out_dir = Path(options.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    har_path = out_dir / "har.json"
    manifest_path = out_dir / "manifest.json"

    launch_kwargs = profile_to_camoufox_kwargs(options.profile)
    if options.proxy is not None:
        launch_kwargs["proxy"] = proxy_to_playwright_dict(options.proxy)

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

    try:
        async with AsyncCamoufox(**launch_kwargs) as browser:
            page = await browser.new_page()

            page.on("request", _on_request)
            page.on("response", lambda r: asyncio.create_task(_on_response(r)))
            page.on("requestfailed", _on_failed)

            timeout_ms = int(options.duration_seconds * 1000) + 30000
            await page.goto(
                options.url,
                wait_until="domcontentloaded",
                timeout=timeout_ms,
            )
            await asyncio.sleep(options.duration_seconds)

            captcha_count = await page.locator(_CAPTCHA_SELECTOR).count()
            captcha_detected = captcha_count > 0
            captcha_signal: str | None = None

            if captcha_detected:
                page_content = await page.content()
                captcha_signal = (
                    _detect_captcha_signal(page_content) or "unknown"
                )

            title = await page.title()
            if "Just a moment" in title:
                captcha_detected = True
                captcha_signal = captcha_signal or "cloudflare"

            user_agent = await page.evaluate("() => navigator.userAgent")
    except Exception as e:
        raise RuntimeError(f"camoufox launch failed: {e}") from e

    har = build_har_from_events(events)
    har_path.write_text(har.model_dump_json(indent=2))

    parsed = urlparse(options.url)
    name = options.name or parsed.hostname or options.url
    capture_time = datetime.now(UTC).isoformat()

    manifest = har_to_manifest(
        har,
        name=name,
        source_url=options.url,
        capture_time=capture_time,
        user_agent=user_agent,
        notes=options.notes,
    )
    manifest_path.write_text(manifest.model_dump_json(indent=2))

    return SniffResult(
        har_path=str(har_path),
        manifest_path=str(manifest_path),
        endpoint_count=len(manifest.endpoints),
        captcha_detected=captcha_detected,
        captcha_signal=captcha_signal,
        duration_seconds=options.duration_seconds,
    )


def build_har_from_events(events: list[dict]) -> HAR:
    """Translate a list of Playwright/camoufox network events into a HAR.

    Public for testability — the sniff loop accumulates events as plain dicts
    and hands them off here so the conversion can be unit-tested without a
    live browser.
    """

    requests: dict[int, dict] = {}
    responses: dict[int, dict] = {}
    failed: dict[int, dict] = {}
    request_order: list[int] = []

    for event in events:
        rid = event["request_id"]
        kind = event["kind"]
        if kind == "request":
            if rid not in requests:
                request_order.append(rid)
            requests[rid] = event
        elif kind == "response":
            responses[rid] = event
        elif kind == "failed":
            failed[rid] = event

    entries: list[HAREntry] = []
    for rid in request_order:
        req = requests[rid]
        resp = responses.get(rid)

        post_data: dict | None = None
        if req.get("post_data"):
            post_data = {
                "mimeType": req.get("headers", {}).get("content-type", ""),
                "text": req["post_data"],
            }

        har_request = HARRequest(
            method=req["method"],
            url=req["url"],
            headers=_headers_to_har(req.get("headers", {})),
            postData=post_data,
        )

        if resp is not None:
            content = {
                "size": resp.get("body_size", 0),
                "mimeType": resp.get("mime_type", ""),
            }
            har_response = HARResponse(
                status=resp["status"],
                headers=_headers_to_har(resp.get("response_headers", {})),
                content=content,
                bodySize=resp.get("body_size", 0),
            )
            try:
                start = datetime.fromisoformat(req["time"])
                end = datetime.fromisoformat(resp["time"])
                elapsed_ms = (end - start).total_seconds() * 1000.0
            except Exception:
                elapsed_ms = 0.0
        else:
            har_response = HARResponse(
                status=0,
                headers=[],
                content={"size": 0, "mimeType": ""},
            )
            elapsed_ms = 0.0

        entries.append(
            HAREntry(
                startedDateTime=req["time"],
                time=elapsed_ms,
                request=har_request,
                response=har_response,
            )
        )

    return HAR(log=HARLog(entries=entries))
