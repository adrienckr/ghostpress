"""Tests for ``ghostpress.codegen.readme`` (README markdown generation)."""

from __future__ import annotations

from ghostpress._types import CodegenSpec, GeneratedCommand
from ghostpress.codegen import readme


def _synthetic_spec() -> CodegenSpec:
    return CodegenSpec(
        name="demo-api",
        package_slug="demo_api",
        source_url="https://api.demo.example.com/",
        base_url="https://api.demo.example.com",
        user_agent=None,
        keep_secrets=False,
        commands=[
            GeneratedCommand(
                name="products",
                method="GET",
                url_template="https://api.demo.example.com/v1/products/{id}",
                path_params=["id"],
                query_params={},
                body_fields={},
                body_is_raw=False,
                headers={},
                description="GET https://api.demo.example.com/v1/products/{id}",
            ),
            GeneratedCommand(
                name="cart-post",
                method="POST",
                url_template="https://api.demo.example.com/v1/cart",
                path_params=[],
                query_params={},
                body_fields={"product_id": "42"},
                body_is_raw=False,
                headers={},
                description="POST https://api.demo.example.com/v1/cart",
            ),
        ],
    )


def test_generate_returns_one_artifact() -> None:
    artifacts = readme.generate(_synthetic_spec())
    assert len(artifacts) == 1


def test_generate_path_is_readme_md() -> None:
    artifacts = readme.generate(_synthetic_spec())
    assert artifacts[0].path == "README.md"


def test_readme_includes_source_url() -> None:
    artifacts = readme.generate(_synthetic_spec())
    assert "https://api.demo.example.com/" in artifacts[0].content


def test_readme_includes_first_command_name() -> None:
    artifacts = readme.generate(_synthetic_spec())
    assert "products" in artifacts[0].content


def test_readme_includes_second_command_name() -> None:
    artifacts = readme.generate(_synthetic_spec())
    assert "cart-post" in artifacts[0].content


def test_readme_includes_install_instructions() -> None:
    artifacts = readme.generate(_synthetic_spec())
    assert "pip install" in artifacts[0].content


def test_readme_not_executable() -> None:
    artifacts = readme.generate(_synthetic_spec())
    assert artifacts[0].executable is False
