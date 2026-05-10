"""Tests for ``ghostpress.sniff.build_har_from_events`` (pure helper)."""

from __future__ import annotations

import pytest

from ghostpress.sniff import build_har_from_events


def _req_event(rid: int, *, time: str = "2026-05-09T12:00:00.000+00:00",
               method: str = "GET", url: str = "https://x/a",
               headers: dict[str, str] | None = None,
               post_data: str | None = None) -> dict:
    return {
        "kind": "request",
        "time": time,
        "request_id": rid,
        "method": method,
        "url": url,
        "headers": headers or {},
        "post_data": post_data,
    }


def _resp_event(rid: int, *, time: str = "2026-05-09T12:00:00.100+00:00",
                method: str = "GET", url: str = "https://x/a",
                status: int = 200, headers: dict[str, str] | None = None,
                mime: str = "application/json", size: int = 0) -> dict:
    return {
        "kind": "response",
        "time": time,
        "request_id": rid,
        "method": method,
        "url": url,
        "status": status,
        "response_headers": headers or {},
        "mime_type": mime,
        "body_size": size,
    }


def test_pairs_request_and_response_by_id():
    events = [_req_event(1), _resp_event(1, status=201)]
    har = build_har_from_events(events)
    assert len(har.log.entries) == 1
    assert har.log.entries[0].response.status == 201


def test_orphan_request_has_status_zero():
    events = [_req_event(1)]
    har = build_har_from_events(events)
    assert len(har.log.entries) == 1
    assert har.log.entries[0].response.status == 0


def test_latest_response_wins_for_same_request_id():
    events = [
        _req_event(1),
        _resp_event(1, status=500),
        _resp_event(1, status=200),
    ]
    har = build_har_from_events(events)
    assert har.log.entries[0].response.status == 200


def test_headers_dict_converted_to_har_list():
    events = [
        _req_event(1, headers={"accept": "application/json", "x-foo": "bar"}),
        _resp_event(1, headers={"content-type": "application/json"}),
    ]
    har = build_har_from_events(events)
    req_headers = har.log.entries[0].request.headers
    assert {"name": "accept", "value": "application/json"} in req_headers
    assert {"name": "x-foo", "value": "bar"} in req_headers
    resp_headers = har.log.entries[0].response.headers
    assert {"name": "content-type", "value": "application/json"} in resp_headers


def test_time_computed_in_milliseconds():
    events = [
        _req_event(1, time="2026-05-09T12:00:00.000+00:00"),
        _resp_event(1, time="2026-05-09T12:00:00.500+00:00"),
    ]
    har = build_har_from_events(events)
    assert har.log.entries[0].time == pytest.approx(500.0, abs=0.5)


def test_time_zero_when_no_response():
    events = [_req_event(1)]
    har = build_har_from_events(events)
    assert har.log.entries[0].time == 0.0


def test_post_data_propagated():
    events = [
        _req_event(1, method="POST", post_data="hello",
                   headers={"content-type": "text/plain"}),
        _resp_event(1, method="POST"),
    ]
    har = build_har_from_events(events)
    pd = har.log.entries[0].request.postData
    assert pd is not None
    assert pd["text"] == "hello"
    assert pd["mimeType"] == "text/plain"


def test_request_order_preserved():
    events = [
        _req_event(1, url="https://x/first"),
        _req_event(2, url="https://x/second"),
        _resp_event(2),
        _resp_event(1),
    ]
    har = build_har_from_events(events)
    urls = [e.request.url for e in har.log.entries]
    assert urls == ["https://x/first", "https://x/second"]


def test_failed_event_does_not_create_orphan_entry():
    events = [_req_event(1), {"kind": "failed", "request_id": 1, "method": "GET",
                              "url": "https://x/a", "headers": {},
                              "time": "2026-05-09T12:00:00.000+00:00"}]
    har = build_har_from_events(events)
    # There is still one entry (the request); response is the orphan placeholder.
    assert len(har.log.entries) == 1


@pytest.mark.integration
def test_sniff_smoke():
    pytest.skip("integration only — run with -m integration")
