"""Proxy configuration helpers.

Camoufox accepts Playwright-shape proxy dicts. This module serializes our
:class:`ProxyConfig` into that shape and validates the server URL.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from ghostpress._types import ProxyConfig

__all__ = ["parse_proxy_url", "proxy_to_playwright_dict"]


def proxy_to_playwright_dict(proxy: ProxyConfig) -> dict[str, Any]:
    """Translate :class:`ProxyConfig` to Playwright's proxy dict.

    Output keys follow Playwright's spec: ``server``, ``bypass``, ``username``,
    ``password``. ``username``/``password`` are extracted from the URL if
    embedded, otherwise taken from the explicit fields.
    """

    clean_server, url_user, url_pass = parse_proxy_url(proxy.server)

    out: dict[str, Any] = {"server": clean_server}

    username = proxy.username if proxy.username is not None else url_user
    password = proxy.password if proxy.password is not None else url_pass

    if username is not None:
        out["username"] = username
    if password is not None:
        out["password"] = password

    if proxy.bypass:
        out["bypass"] = ",".join(proxy.bypass)

    return out


def parse_proxy_url(url: str) -> tuple[str, str | None, str | None]:
    """Split ``scheme://user:pass@host:port`` into ``(server, user, pass)``.

    Returns a tuple where ``server`` is the URL without credentials and the
    user/pass are optional. Used internally; exposed for tests.
    """

    if not url:
        return ("", None, None)

    parsed = urlparse(url)

    # If parsing produced no netloc (e.g. "host:port" without scheme), return
    # the input unchanged.
    if not parsed.netloc:
        return (url, None, None)

    username = parsed.username
    password = parsed.password

    host = parsed.hostname or ""
    clean_netloc = f"{host}:{parsed.port}" if parsed.port is not None else host

    clean_server = urlunparse((parsed.scheme, clean_netloc, "", "", "", ""))

    return (clean_server, username, password)
