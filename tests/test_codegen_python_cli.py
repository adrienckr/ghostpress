"""Tests for ``ghostpress.codegen.python_cli`` (CLI source generation)."""

from __future__ import annotations

import ast

from ghostpress._types import CodegenSpec, GeneratedCommand
from ghostpress.codegen import python_cli


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
                headers={"Accept": "application/json"},
                description="GET https://api.demo.example.com/v1/products/{id}",
            ),
            GeneratedCommand(
                name="cart-post",
                method="POST",
                url_template="https://api.demo.example.com/v1/cart",
                path_params=[],
                query_params={},
                body_fields={"product_id": "42", "quantity": "1"},
                body_is_raw=False,
                headers={"Content-Type": "application/json"},
                description="POST https://api.demo.example.com/v1/cart",
            ),
        ],
    )


def test_generate_returns_two_artifacts() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    assert len(artifacts) == 2


def test_generate_includes_cli_py_artifact() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    paths = {a.path for a in artifacts}
    assert "cli.py" in paths


def test_generate_includes_pyproject_artifact() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    paths = {a.path for a in artifacts}
    assert "pyproject.toml" in paths


def test_cli_py_content_non_empty() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    assert cli_py.content.strip() != ""


def test_cli_py_parses_as_valid_python() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    ast.parse(cli_py.content)


def test_cli_py_contains_first_command_marker() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    assert '@app.command("products"' in cli_py.content


def test_cli_py_contains_second_command_marker() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    assert '@app.command("cart-post"' in cli_py.content


def test_cli_py_includes_url_template() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    assert "https://api.demo.example.com/v1/products/{id}" in cli_py.content


def test_cli_py_path_param_in_signature() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    assert "id: str = typer.Argument" in cli_py.content


def test_cli_py_body_field_as_typer_option() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    assert '"--product_id"' in cli_py.content or '"--product-id"' in cli_py.content


def test_cli_py_executable_flag_set() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    cli_py = next(a for a in artifacts if a.path == "cli.py")
    assert cli_py.executable is True


def test_pyproject_includes_slug() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    pyproject = next(a for a in artifacts if a.path == "pyproject.toml")
    assert 'name = "demo_api"' in pyproject.content


def test_pyproject_references_source_url() -> None:
    artifacts = python_cli.generate(_synthetic_spec())
    pyproject = next(a for a in artifacts if a.path == "pyproject.toml")
    assert "https://api.demo.example.com/" in pyproject.content
