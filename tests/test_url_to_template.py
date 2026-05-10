"""Tests for ``ghostpress.manifest.url_to_template``."""

from __future__ import annotations

import pytest

from ghostpress.manifest import url_to_template


def test_numeric_segment_becomes_id():
    assert (
        url_to_template("https://api.example.com/v1/users/42")
        == "https://api.example.com/v1/users/{id}"
    )


def test_numeric_only_at_end():
    assert (
        url_to_template("https://api.example.com/orders/9")
        == "https://api.example.com/orders/{id}"
    )


def test_uuid_segment_becomes_uuid():
    assert (
        url_to_template(
            "https://api.example.com/orders/123e4567-e89b-12d3-a456-426614174000"
        )
        == "https://api.example.com/orders/{uuid}"
    )


def test_query_string_dropped():
    assert (
        url_to_template("https://api.example.com/v1/products?expand=1")
        == "https://api.example.com/v1/products"
    )


def test_fragment_dropped():
    assert (
        url_to_template("https://api.example.com/v1/products#section")
        == "https://api.example.com/v1/products"
    )


def test_host_lowercased():
    assert (
        url_to_template("HTTPS://API.EXAMPLE.COM/foo")
        == "https://api.example.com/foo"
    )


def test_path_case_preserved():
    assert (
        url_to_template("https://api.example.com/V1/Users")
        == "https://api.example.com/V1/Users"
    )


def test_mixed_numeric_and_uuid():
    url = (
        "https://api.example.com/v1/users/42/orders/"
        "123e4567-e89b-12d3-a456-426614174000"
    )
    assert (
        url_to_template(url)
        == "https://api.example.com/v1/users/{id}/orders/{uuid}"
    )


def test_non_numeric_non_uuid_preserved():
    assert (
        url_to_template("https://api.example.com/users/alice")
        == "https://api.example.com/users/alice"
    )


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://api.example.com/", "https://api.example.com/"),
        (
            "https://api.example.com/v2/items/100/details",
            "https://api.example.com/v2/items/{id}/details",
        ),
    ],
)
def test_parametrized_templates(url: str, expected: str) -> None:
    assert url_to_template(url) == expected
