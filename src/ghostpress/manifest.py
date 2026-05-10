"""HAR → printing-press-compatible endpoint manifest.

The conversion is deterministic and pure: same HAR → same manifest. That
matters because the manifest is used to generate code downstream, and stable
output keeps generated CLIs reproducible.
"""

from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import urlparse, urlunparse

from ghostpress._types import HAR, Endpoint, EndpointSample, HAREntry, Manifest

__all__ = ["extract_endpoints", "har_to_manifest", "url_to_template"]


_ALLOWED_MIME_PREFIXES = (
    "application/json",
    "text/json",
    "application/x-www-form-urlencoded",
)
_PREVIEW_LIMIT = 4096
_NUMERIC_SEGMENT = re.compile(r"^\d+$")
_UUID_SEGMENT = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def har_to_manifest(
    har: HAR,
    *,
    name: str,
    source_url: str,
    capture_time: str,
    user_agent: str | None = None,
    notes: str | None = None,
) -> Manifest:
    """Convert a :class:`HAR` to a :class:`Manifest`.

    Implementation responsibilities:

    1. Filter HAR entries: keep only ``application/json``, ``text/json``, and
       ``application/x-www-form-urlencoded`` responses by default; static
       assets (JS/CSS/images/fonts) are dropped.
    2. Group entries by (method, normalized URL template). Use
       :func:`url_to_template` to collapse query params and numeric path
       segments into placeholders.
    3. For each group, pick the first 200-OK response as the
       :class:`EndpointSample`. Cap header/body previews at 4 KB so manifests
       stay small.
    4. Produce a stable order: sort endpoints by (method, url_template).

    Returns a fully populated :class:`Manifest`.
    """

    endpoints = extract_endpoints(har)
    return Manifest(
        schema_version=1,
        name=name,
        source_url=source_url,
        capture_time=capture_time,
        user_agent=user_agent,
        endpoints=endpoints,
        notes=notes,
    )


def extract_endpoints(har: HAR) -> list[Endpoint]:
    """Public wrapper around the grouping step. Used by tests."""

    groups: dict[tuple[str, str], list[HAREntry]] = defaultdict(list)

    for entry in har.log.entries:
        if entry.response.status == 0:
            continue
        mime_type = entry.response.content.get("mimeType", "") or ""
        if not mime_type.startswith(_ALLOWED_MIME_PREFIXES):
            continue
        method = entry.request.method.upper()
        template = url_to_template(entry.request.url)
        groups[(method, template)].append(entry)

    endpoints: list[Endpoint] = []
    for (method, template), group in groups.items():
        content_type: str | None = None
        for entry in group:
            mime_type = entry.response.content.get("mimeType", "") or ""
            if mime_type:
                content_type = mime_type
                break

        sample_entry = next(
            (e for e in group if e.response.status == 200),
            group[0],
        )
        endpoints.append(
            Endpoint(
                method=method,
                url_template=template,
                response_content_type=content_type,
                request_count=len(group),
                sample=_build_sample(sample_entry),
            )
        )

    endpoints.sort(key=lambda e: (e.method, e.url_template))
    return endpoints


def url_to_template(url: str) -> str:
    """Normalize a URL into an endpoint template.

    Rules:

    * Strip query string.
    * Replace numeric path segments with ``{id}``.
    * Replace UUID-shaped segments with ``{uuid}``.
    * Lowercase the host; preserve path case.

    Examples:

    >>> url_to_template("https://api.example.com/v1/users/42?expand=1")
    'https://api.example.com/v1/users/{id}'
    >>> url_to_template("https://api.example.com/orders/9d8a-...-uuid")
    'https://api.example.com/orders/{uuid}'
    """

    parsed = urlparse(url)
    netloc = parsed.netloc.lower()

    segments = parsed.path.split("/")
    rewritten = []
    for segment in segments:
        if not segment:
            rewritten.append(segment)
        elif _NUMERIC_SEGMENT.match(segment):
            rewritten.append("{id}")
        elif _UUID_SEGMENT.match(segment):
            rewritten.append("{uuid}")
        else:
            rewritten.append(segment)
    path = "/".join(rewritten)

    return urlunparse((parsed.scheme, netloc, path, parsed.params, "", ""))


def _build_sample(entry: HAREntry) -> EndpointSample:
    """Construct an :class:`EndpointSample` from a single HAR entry."""

    request_headers = _headers_to_dict(entry.request.headers)
    response_headers = _headers_to_dict(entry.response.headers)

    request_body_preview: str | None = None
    if entry.request.postData:
        body_text = entry.request.postData.get("text")
        if body_text is not None:
            request_body_preview = str(body_text)[:_PREVIEW_LIMIT]

    response_text = entry.response.content.get("text")
    response_body_preview: str | None = None
    if response_text is not None:
        response_body_preview = str(response_text)[:_PREVIEW_LIMIT]

    declared_size = entry.response.content.get("size")
    if isinstance(declared_size, int) and declared_size > 0:
        response_size_bytes = declared_size
    else:
        response_size_bytes = len(response_text or "")

    return EndpointSample(
        status=entry.response.status,
        request_headers=request_headers,
        request_body_preview=request_body_preview,
        response_headers=response_headers,
        response_body_preview=response_body_preview,
        response_size_bytes=response_size_bytes,
    )


def _headers_to_dict(headers: list[dict]) -> dict[str, str]:
    """Flatten a HAR header list to a dict (first occurrence wins)."""

    flat: dict[str, str] = {}
    for header in headers:
        name = header.get("name")
        value = header.get("value")
        if not name:
            continue
        if name in flat:
            continue
        flat[name] = "" if value is None else str(value)
    return flat
