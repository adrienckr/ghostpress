"""Tests for ``ghostpress.codegen.claude_skill`` (skill markdown generation)."""

from __future__ import annotations

from ghostpress._types import CodegenSpec, GeneratedCommand
from ghostpress.codegen import claude_skill


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
    artifacts = claude_skill.generate(_synthetic_spec())
    assert len(artifacts) == 1


def test_generate_path_is_skill_md() -> None:
    artifacts = claude_skill.generate(_synthetic_spec())
    assert artifacts[0].path == "skill.md"


def test_skill_md_frontmatter_has_name() -> None:
    artifacts = claude_skill.generate(_synthetic_spec())
    assert "name: demo-api" in artifacts[0].content


def test_skill_md_frontmatter_has_description() -> None:
    artifacts = claude_skill.generate(_synthetic_spec())
    assert "description:" in artifacts[0].content


def test_skill_md_starts_with_frontmatter_delimiter() -> None:
    artifacts = claude_skill.generate(_synthetic_spec())
    assert artifacts[0].content.startswith("---")


def test_skill_md_contains_first_command_section() -> None:
    artifacts = claude_skill.generate(_synthetic_spec())
    assert "`products`" in artifacts[0].content


def test_skill_md_contains_second_command_section() -> None:
    artifacts = claude_skill.generate(_synthetic_spec())
    assert "`cart-post`" in artifacts[0].content


def test_skill_md_not_executable() -> None:
    artifacts = claude_skill.generate(_synthetic_spec())
    assert artifacts[0].executable is False
