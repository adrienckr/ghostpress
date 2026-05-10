"""Manifest -> Claude Code skill markdown.

Emits a ``skill.md`` with frontmatter (name, description) and a body that
documents every endpoint as a callable action, including the matching
``stealth_*`` MCP tool name when relevant.
"""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment

from ghostpress._types import CodegenSpec, GeneratedArtifact

__all__ = ["generate"]


def generate(spec: CodegenSpec) -> list[GeneratedArtifact]:
    """Render the Claude Code skill.

    Returns ``[GeneratedArtifact(path='skill.md', content=<rendered>)]``.
    Drop-in for ``~/.claude/skills/<name>/skill.md``.
    """

    tpl_text = (files("ghostpress.templates") / "skill.md.jinja").read_text()
    env = Environment(autoescape=False, trim_blocks=False, lstrip_blocks=False)
    template = env.from_string(tpl_text)
    rendered = template.render(spec=spec)
    return [GeneratedArtifact(path="skill.md", content=rendered, executable=False)]
