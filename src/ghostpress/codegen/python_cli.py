"""Manifest -> standalone Typer CLI Python source.

The generated CLI:

- Has zero dependency on ghostpress itself.
- Imports only ``typer``, ``httpx``, ``rich``.
- One Typer command per :class:`GeneratedCommand`.
- Path placeholders → Typer arguments. Query params → Typer options.
- Body fields → either ``--field`` flags (JSON dict) or ``--body @file`` (raw).
- Replays sanitized headers (no auth unless ``keep_secrets`` was set at build).
"""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment

from ghostpress._types import CodegenSpec, GeneratedArtifact

__all__ = ["generate"]


_PYPROJECT_TEMPLATE = """\
[project]
name = "{slug}"
version = "0.1.0"
description = "Generated CLI for {source_url}"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12.0",
    "httpx>=0.27.0",
    "rich>=13.0.0",
]

[project.scripts]
{slug} = "{slug}.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""


def generate(spec: CodegenSpec) -> list[GeneratedArtifact]:
    """Render the Typer CLI source.

    Returns ``[GeneratedArtifact(path='cli.py', content=<rendered>, executable=True)]``
    plus a ``pyproject.toml`` artifact pinning the CLI's own deps so users can
    install the generated CLI as a standalone tool.
    """

    template_text = (
        files("ghostpress.templates").joinpath("cli.py.jinja").read_text(encoding="utf-8")
    )

    env = Environment(
        autoescape=False,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    template = env.from_string(template_text)
    rendered = template.render(spec=spec)

    pyproject_text = _PYPROJECT_TEMPLATE.format(
        slug=spec.package_slug,
        source_url=spec.source_url,
    )

    return [
        GeneratedArtifact(path="cli.py", content=rendered, executable=True),
        GeneratedArtifact(path="pyproject.toml", content=pyproject_text),
    ]
