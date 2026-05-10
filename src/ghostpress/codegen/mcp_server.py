"""Manifest -> standalone MCP server Python source.

Mirrors python_cli.generate but emits an MCP stdio server that exposes one
tool per endpoint with the same inferred input schema.
"""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment

from ghostpress._types import CodegenSpec, GeneratedArtifact

__all__ = ["generate"]


def generate(spec: CodegenSpec) -> list[GeneratedArtifact]:
    """Render the MCP server source.

    Returns ``[GeneratedArtifact(path='mcp.py', content=<rendered>, executable=True)]``.
    The generated file uses ``from mcp.server import Server`` and the same
    ``stdio_server`` shape ghostpress's own MCP server uses.
    """

    tpl_text = (files("ghostpress.templates") / "mcp.py.jinja").read_text()
    env = Environment(autoescape=False, trim_blocks=False, lstrip_blocks=False)
    template = env.from_string(tpl_text)
    rendered = template.render(spec=spec)
    return [GeneratedArtifact(path="mcp.py", content=rendered, executable=True)]
