"""Tests for ``ghostpress.manifest`` (extract_endpoints + har_to_manifest)."""

from __future__ import annotations

from typing import Any

from ghostpress._types import (
    HAR,
    HAREntry,
    HARLog,
    HARRequest,
    HARResponse,
)
from ghostpress.manifest import extract_endpoints, har_to_manifest


def _entry(
    *,
    method: str = "GET",
    url: str = "https://api.example.com/v1/things",
    status: int = 200,
    mime: str = "application/json",
    body: str = "{}",
    started: str = "2026-05-09T12:00:00.000Z",
    request_headers: list[dict[str, str]] | None = None,
    response_headers: list[dict[str, str]] | None = None,
    post_data: dict[str, Any] | None = None,
    size: int | None = None,
) -> HAREntry:
    return HAREntry(
        startedDateTime=started,
        time=10.0,
        request=HARRequest(
            method=method,
            url=url,
            headers=request_headers or [],
            postData=post_data,
        ),
        response=HARResponse(
            status=status,
            headers=response_headers or [],
            content={
                "size": size if size is not None else len(body),
                "mimeType": mime,
                "text": body,
            },
        ),
    )


def _har(entries: list[HAREntry]) -> HAR:
    return HAR(log=HARLog(entries=entries))


def test_extract_filters_image_png():
    har = _har(
        [
            _entry(url="https://x/a.json", mime="application/json"),
            _entry(url="https://x/b.png", mime="image/png"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert len(endpoints) == 1
    assert endpoints[0].url_template == "https://x/a.json"


def test_extract_filters_text_html():
    har = _har(
        [
            _entry(url="https://x/a", mime="application/json"),
            _entry(url="https://x/b", mime="text/html"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert len(endpoints) == 1


def test_extract_filters_javascript():
    har = _har(
        [
            _entry(url="https://x/a", mime="application/json"),
            _entry(url="https://x/app.js", mime="application/javascript"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert len(endpoints) == 1


def test_extract_skips_status_zero():
    har = _har(
        [
            _entry(url="https://x/a", status=0, mime="application/json"),
            _entry(url="https://x/b", status=200, mime="application/json"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert len(endpoints) == 1
    assert endpoints[0].url_template == "https://x/b"


def test_grouping_collapses_numeric_ids():
    har = _har(
        [
            _entry(url="https://x/users/1", mime="application/json"),
            _entry(url="https://x/users/2", mime="application/json"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert len(endpoints) == 1
    assert endpoints[0].url_template == "https://x/users/{id}"
    assert endpoints[0].request_count == 2


def test_method_normalization_lower_and_upper_collapse():
    har = _har(
        [
            _entry(method="get", url="https://x/a", mime="application/json"),
            _entry(method="GET", url="https://x/a", mime="application/json"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert len(endpoints) == 1
    assert endpoints[0].method == "GET"
    assert endpoints[0].request_count == 2


def test_sample_picks_first_200():
    har = _har(
        [
            _entry(url="https://x/a", status=500, mime="application/json", body="err"),
            _entry(url="https://x/a", status=200, mime="application/json", body="ok-1"),
            _entry(url="https://x/a", status=200, mime="application/json", body="ok-2"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert endpoints[0].sample is not None
    assert endpoints[0].sample.status == 200
    assert endpoints[0].sample.response_body_preview == "ok-1"


def test_sample_falls_back_to_first_when_no_200():
    har = _har(
        [
            _entry(url="https://x/a", status=404, mime="application/json", body="nf"),
            _entry(url="https://x/a", status=500, mime="application/json", body="err"),
        ]
    )
    endpoints = extract_endpoints(har)
    assert endpoints[0].sample is not None
    assert endpoints[0].sample.status == 404


def test_sort_order_is_deterministic():
    har = _har(
        [
            _entry(method="POST", url="https://x/z", mime="application/json"),
            _entry(method="GET", url="https://x/a", mime="application/json"),
            _entry(method="GET", url="https://x/b", mime="application/json"),
        ]
    )
    endpoints = extract_endpoints(har)
    keys = [(e.method, e.url_template) for e in endpoints]
    assert keys == sorted(keys)


def test_har_to_manifest_schema_version_is_1(sample_har: HAR):
    manifest = har_to_manifest(
        sample_har,
        name="test",
        source_url="https://api.example.com",
        capture_time="2026-05-09T12:00:00Z",
    )
    assert manifest.schema_version == 1


def test_har_to_manifest_populates_top_fields(sample_har: HAR):
    manifest = har_to_manifest(
        sample_har,
        name="test-name",
        source_url="https://api.example.com",
        capture_time="2026-05-09T12:00:00Z",
        user_agent="ua/1.0",
        notes="hi",
    )
    assert manifest.name == "test-name"
    assert manifest.source_url == "https://api.example.com"
    assert manifest.capture_time == "2026-05-09T12:00:00Z"
    assert manifest.user_agent == "ua/1.0"
    assert manifest.notes == "hi"


def test_har_to_manifest_filters_static_assets(sample_har: HAR):
    manifest = har_to_manifest(
        sample_har,
        name="t",
        source_url="https://api.example.com",
        capture_time="2026-05-09T12:00:00Z",
    )
    templates = {e.url_template for e in manifest.endpoints}
    assert "https://api.example.com/static/app.js" not in templates
    assert "https://api.example.com/page" not in templates


def test_har_to_manifest_endpoint_count(sample_har: HAR):
    manifest = har_to_manifest(
        sample_har,
        name="t",
        source_url="https://api.example.com",
        capture_time="2026-05-09T12:00:00Z",
    )
    # 3 GETs + 1 POST = 4 unique JSON endpoints (404 is application/json too).
    assert len(manifest.endpoints) == 4


def test_body_preview_truncated_at_4096():
    big = "x" * 5000
    har = _har([_entry(url="https://x/a", mime="application/json", body=big)])
    endpoints = extract_endpoints(har)
    assert endpoints[0].sample is not None
    assert len(endpoints[0].sample.response_body_preview) == 4096


def test_request_body_preview_truncated_at_4096():
    big = "y" * 5000
    har = _har(
        [
            _entry(
                method="POST",
                url="https://x/a",
                mime="application/json",
                post_data={"mimeType": "application/json", "text": big},
            )
        ]
    )
    endpoints = extract_endpoints(har)
    assert endpoints[0].sample is not None
    assert len(endpoints[0].sample.request_body_preview) == 4096
