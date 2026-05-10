"""Tests for the Pydantic models in ``ghostpress._types``."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from ghostpress._types import (
    HAR,
    BrowserProfile,
    Flow,
    FlowStep,
    HARLog,
    Manifest,
    ProxyConfig,
)


def test_har_round_trip_empty():
    har = HAR(log=HARLog())
    dumped = har.model_dump()
    rehydrated = HAR.model_validate(dumped)
    assert rehydrated.log.entries == []


def test_har_round_trip_keeps_version():
    har = HAR(log=HARLog())
    rehydrated = HAR.model_validate(har.model_dump())
    assert rehydrated.log.version == "1.2"


def test_manifest_v1_fixture_loads(manifest_v1_path: Path):
    raw = manifest_v1_path.read_text()
    manifest = Manifest.model_validate_json(raw)
    assert manifest.schema_version == 1


def test_manifest_v1_fixture_has_endpoints(manifest_v1_path: Path):
    manifest = Manifest.model_validate_json(manifest_v1_path.read_text())
    assert len(manifest.endpoints) > 0


def test_browser_profile_default_headless():
    profile = BrowserProfile()
    assert profile.headless is True


def test_browser_profile_default_geoip():
    profile = BrowserProfile()
    assert profile.geoip is True


def test_browser_profile_default_locale_none():
    profile = BrowserProfile()
    assert profile.locale is None


def test_browser_profile_default_extra_launch_args_empty():
    profile = BrowserProfile()
    assert profile.extra_launch_args == {}


def test_proxy_config_requires_server():
    with pytest.raises(ValidationError):
        ProxyConfig()  # type: ignore[call-arg]


def test_proxy_config_minimal_ok():
    cfg = ProxyConfig(server="http://host:8080")
    assert cfg.server == "http://host:8080"
    assert cfg.username is None
    assert cfg.password is None
    assert cfg.bypass == []


def test_flow_round_trip_through_model_validate():
    data = {
        "name": "demo",
        "description": "tiny flow",
        "steps": [
            {"action": "navigate", "args": {"url": "https://example.com"}},
            {"action": "screenshot", "args": {"full_page": True}, "name": "shot"},
        ],
    }
    flow = Flow.model_validate(data)
    assert flow.name == "demo"
    assert len(flow.steps) == 2
    assert flow.steps[0].action == "navigate"
    assert flow.steps[1].name == "shot"


def test_flow_step_round_trip():
    data = {"action": "click", "args": {"selector": "#go"}}
    step = FlowStep.model_validate(data)
    assert step.action == "click"
    assert step.args == {"selector": "#go"}
