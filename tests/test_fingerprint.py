"""Tests for ``ghostpress.fingerprint``."""

from __future__ import annotations

from ghostpress._types import BrowserProfile
from ghostpress.fingerprint import default_profile, profile_to_camoufox_kwargs


def test_default_profile_headless_true():
    assert default_profile().headless is True


def test_default_profile_geoip_true():
    assert default_profile().geoip is True


def test_kwargs_for_default_profile():
    kwargs = profile_to_camoufox_kwargs(BrowserProfile())
    assert kwargs == {"headless": True, "geoip": True}


def test_kwargs_with_viewport_includes_screen_and_window():
    kwargs = profile_to_camoufox_kwargs(BrowserProfile(viewport=(1280, 720)))
    assert kwargs["screen"] == {"width": 1280, "height": 720}
    assert kwargs["window"] == {"width": 1280, "height": 720}


def test_kwargs_propagates_locale():
    kwargs = profile_to_camoufox_kwargs(BrowserProfile(locale="fr-FR"))
    assert kwargs["locale"] == "fr-FR"


def test_kwargs_propagates_timezone():
    kwargs = profile_to_camoufox_kwargs(BrowserProfile(timezone="Europe/Paris"))
    assert kwargs["timezone"] == "Europe/Paris"


def test_kwargs_omits_locale_when_none():
    kwargs = profile_to_camoufox_kwargs(BrowserProfile())
    assert "locale" not in kwargs


def test_kwargs_omits_timezone_when_none():
    kwargs = profile_to_camoufox_kwargs(BrowserProfile())
    assert "timezone" not in kwargs


def test_kwargs_propagates_user_data_dir():
    kwargs = profile_to_camoufox_kwargs(BrowserProfile(user_data_dir="/tmp/d"))
    assert kwargs["user_data_dir"] == "/tmp/d"


def test_extra_launch_args_merged():
    kwargs = profile_to_camoufox_kwargs(
        BrowserProfile(extra_launch_args={"foo": "bar"})
    )
    assert kwargs["foo"] == "bar"


def test_extra_launch_args_can_override():
    kwargs = profile_to_camoufox_kwargs(
        BrowserProfile(extra_launch_args={"headless": False, "custom": 1})
    )
    assert kwargs["headless"] is False
    assert kwargs["custom"] == 1
