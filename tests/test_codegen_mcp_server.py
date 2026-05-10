"""Tests for ``ghostpress.codegen.mcp_server`` (MCP source generation)."""

from __future__ import annotations

import ast

from ghostpress._types import CodegenSpec, GeneratedCommand
from ghostpress.codegen import mcp_server


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
                body_fields={"product_id": "42"},
                body_is_raw=False,
                headers={"Content-Type": "application/json"},
                description="POST https://api.demo.example.com/v1/cart",
            ),
        ],
    )


def test_generate_returns_one_artifact() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert len(artifacts) == 1


def test_generate_path_is_mcp_py() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert artifacts[0].path == "mcp.py"


def test_mcp_py_parses_as_valid_python() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    ast.parse(artifacts[0].content)


def test_mcp_py_imports_server() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert "from mcp.server import Server" in artifacts[0].content


def test_mcp_py_uses_list_tools_decorator() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert "@server.list_tools()" in artifacts[0].content


def test_mcp_py_uses_call_tool_decorator() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert "@server.call_tool()" in artifacts[0].content


def test_mcp_py_uses_stdio_server() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert "stdio_server" in artifacts[0].content


def test_mcp_py_tool_name_with_underscore_for_dashed_command() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert 'name="cart_post"' in artifacts[0].content


def test_mcp_py_first_tool_name_present() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert 'name="products"' in artifacts[0].content


def test_mcp_py_executable_flag_set() -> None:
    artifacts = mcp_server.generate(_synthetic_spec())
    assert artifacts[0].executable is True
