"""Tests for ``ghostpress.codegen._utils`` (slugify, package_slug, header sanitization)."""

from __future__ import annotations

import pytest

from ghostpress.codegen._utils import (
    command_name_from_endpoint,
    extract_path_params,
    package_slug,
    sanitize_headers,
    slugify,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Hello World", "hello-world"),
        ("foo_bar", "foo-bar"),
        ("", ""),
        ("!!!", ""),
        ("foo--bar", "foo-bar"),
    ],
)
def test_slugify_cases(value: str, expected: str) -> None:
    assert slugify(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", "_"),
        ("my-cli", "my_cli"),
        ("123foo", "_123foo"),
        ("FooBar", "foobar"),
        ("!!!", "_"),
    ],
)
def test_package_slug_cases(value: str, expected: str) -> None:
    assert package_slug(value) == expected


def test_extract_path_params_multiple() -> None:
    assert extract_path_params("/users/{id}/posts/{post_id}") == ["id", "post_id"]


def test_extract_path_params_none() -> None:
    assert extract_path_params("/foo") == []


def test_sanitize_headers_drops_authorization() -> None:
    headers = {"Authorization": "Bearer x", "Accept": "application/json"}
    out = sanitize_headers(headers, keep_secrets=False)
    assert "Authorization" not in out


def test_sanitize_headers_drops_cookie_case_insensitive() -> None:
    headers = {"cookie": "session=1", "accept": "application/json"}
    out = sanitize_headers(headers, keep_secrets=False)
    assert "cookie" not in out


def test_sanitize_headers_drops_x_api_key_case_insensitive() -> None:
    headers = {"X-Api-Key": "secret", "Accept": "application/json"}
    out = sanitize_headers(headers, keep_secrets=False)
    assert "X-Api-Key" not in out


def test_sanitize_headers_preserves_content_type() -> None:
    headers = {"Authorization": "Bearer x", "Content-Type": "application/json"}
    out = sanitize_headers(headers, keep_secrets=False)
    assert out["Content-Type"] == "application/json"


def test_sanitize_headers_preserves_accept() -> None:
    headers = {"Authorization": "Bearer x", "Accept": "application/json"}
    out = sanitize_headers(headers, keep_secrets=False)
    assert out["Accept"] == "application/json"


def test_sanitize_headers_keep_secrets_retains_authorization() -> None:
    headers = {"Authorization": "Bearer x", "Accept": "application/json"}
    out = sanitize_headers(headers, keep_secrets=True)
    assert out["Authorization"] == "Bearer x"


def test_command_name_from_get_users() -> None:
    taken: set[str] = set()
    name = command_name_from_endpoint("GET", "/users", taken=taken)
    assert name == "users"


def test_command_name_from_post_users_appends_method() -> None:
    taken: set[str] = set()
    name = command_name_from_endpoint("POST", "/users", taken=taken)
    assert name == "users-post"


def test_command_name_skips_path_placeholder() -> None:
    taken: set[str] = set()
    name = command_name_from_endpoint("GET", "/users/{id}", taken=taken)
    assert name == "users"


def test_command_name_collision_first_wins() -> None:
    taken: set[str] = set()
    first = command_name_from_endpoint("GET", "/users", taken=taken)
    second = command_name_from_endpoint("GET", "/users", taken=taken)
    assert first == "users"
    assert second == "users-1"


def test_command_name_mutates_taken_set() -> None:
    taken: set[str] = set()
    command_name_from_endpoint("GET", "/users", taken=taken)
    assert "users" in taken
