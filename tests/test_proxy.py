"""Tests for ``ghostpress.proxy``."""

from __future__ import annotations

from ghostpress._types import ProxyConfig
from ghostpress.proxy import parse_proxy_url, proxy_to_playwright_dict


def test_parse_empty_string():
    assert parse_proxy_url("") == ("", None, None)


def test_parse_http_no_creds():
    assert parse_proxy_url("http://host:8080") == ("http://host:8080", None, None)


def test_parse_http_with_creds():
    server, user, password = parse_proxy_url("http://user:pass@host:8080")
    assert server == "http://host:8080"
    assert user == "user"
    assert password == "pass"


def test_parse_socks5():
    server, user, password = parse_proxy_url("socks5://host:1080")
    assert server == "socks5://host:1080"
    assert user is None
    assert password is None


def test_parse_socks5_with_creds():
    server, user, password = parse_proxy_url("socks5://u:p@host:1080")
    assert server == "socks5://host:1080"
    assert user == "u"
    assert password == "p"


def test_proxy_dict_with_url_creds():
    cfg = ProxyConfig(server="http://user:pass@host:8080")
    d = proxy_to_playwright_dict(cfg)
    assert d["server"] == "http://host:8080"
    assert d["username"] == "user"
    assert d["password"] == "pass"


def test_proxy_dict_explicit_overrides_url():
    cfg = ProxyConfig(
        server="http://urluser:urlpass@host:8080",
        username="explicit_user",
        password="explicit_pass",
    )
    d = proxy_to_playwright_dict(cfg)
    assert d["username"] == "explicit_user"
    assert d["password"] == "explicit_pass"


def test_proxy_dict_no_creds_omitted():
    cfg = ProxyConfig(server="http://host:8080")
    d = proxy_to_playwright_dict(cfg)
    assert "username" not in d
    assert "password" not in d


def test_proxy_dict_bypass_joined():
    cfg = ProxyConfig(server="http://host:8080", bypass=["a.com", "b.com"])
    d = proxy_to_playwright_dict(cfg)
    assert d["bypass"] == "a.com,b.com"


def test_proxy_dict_bypass_omitted_when_empty():
    cfg = ProxyConfig(server="http://host:8080")
    d = proxy_to_playwright_dict(cfg)
    assert "bypass" not in d


def test_proxy_dict_clean_server_strips_creds():
    cfg = ProxyConfig(server="http://u:p@host:8080")
    d = proxy_to_playwright_dict(cfg)
    assert "@" not in d["server"]
