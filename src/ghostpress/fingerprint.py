"""Per-session browser profile helpers.

Camoufox auto-generates fingerprint internals via BrowserForge, so this module
is intentionally thin: it normalizes the high-level :class:`BrowserProfile`
into the keyword arguments that :class:`camoufox.async_api.AsyncCamoufox`
accepts.
"""

from __future__ import annotations

from typing import Any

from ghostpress._types import BrowserProfile

__all__ = ["default_profile", "profile_to_camoufox_kwargs"]


def profile_to_camoufox_kwargs(profile: BrowserProfile) -> dict[str, Any]:
    """Translate a :class:`BrowserProfile` into camoufox launcher kwargs.

    Implementation responsibilities:

    * Map ``headless``, ``locale``, ``timezone``, ``geoip``, ``viewport``,
      ``user_data_dir`` to their camoufox-equivalent kwargs.
    * Merge ``profile.extra_launch_args`` last so the operator can override.
    * When ``geoip=True`` and a proxy is in play, the *caller* must pass the
      proxy through to camoufox so its bundled geoip lookup picks the right
      timezone/locale; this function does not handle proxies.
    """

    kwargs: dict[str, Any] = {
        "headless": profile.headless,
        "geoip": profile.geoip,
    }

    if profile.locale is not None:
        kwargs["locale"] = profile.locale

    if profile.timezone is not None:
        kwargs["timezone"] = profile.timezone

    if profile.viewport is not None:
        width, height = profile.viewport
        kwargs["screen"] = {"width": width, "height": height}
        kwargs["window"] = {"width": width, "height": height}

    if profile.user_data_dir is not None:
        kwargs["user_data_dir"] = profile.user_data_dir

    kwargs.update(profile.extra_launch_args)
    return kwargs


def default_profile() -> BrowserProfile:
    """A reasonable default profile: headless, geoip-on, no fixed locale."""

    return BrowserProfile(headless=True, geoip=True)
