"""Manifest -> per-CLI README.

Emits a README.md that goes inside the generated artifact directory, with
install instructions, every command documented, and an example invocation
for each.
"""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment

from ghostpress._types import CodegenSpec, GeneratedArtifact

__all__ = ["generate"]


def generate(spec: CodegenSpec) -> list[GeneratedArtifact]:
    """Render the per-CLI README.

    Returns ``[GeneratedArtifact(path='README.md', content=<rendered>)]``.
    """

    tpl_text = (files("ghostpress.templates") / "readme.md.jinja").read_text()
    env = Environment(autoescape=False, trim_blocks=False, lstrip_blocks=False)
    template = env.from_string(tpl_text)
    rendered = template.render(spec=spec)
    return [GeneratedArtifact(path="README.md", content=rendered, executable=False)]
