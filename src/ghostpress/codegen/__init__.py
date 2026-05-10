"""Codegen modules — Manifest -> generated artifacts (CLI, MCP, Skill, README).

Public surface:

- :func:`spec_from_manifest` — pure deterministic translation of a
  :class:`ghostpress._types.Manifest` into a :class:`CodegenSpec` that every
  codegen module consumes.
- One ``generate(spec) -> list[GeneratedArtifact]`` per format module.
- :func:`generate_all` — fan-out over the requested formats.
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

from ghostpress._types import (
    CodegenSpec,
    GeneratedArtifact,
    GeneratedCommand,
    Manifest,
)
from ghostpress.codegen._utils import (
    command_name_from_endpoint,
    extract_path_params,
    package_slug,
    sanitize_headers,
)

__all__ = [
    "generate_all",
    "spec_from_manifest",
]


def spec_from_manifest(
    manifest: Manifest,
    *,
    name: str | None = None,
    keep_secrets: bool = False,
) -> CodegenSpec:
    """Translate a :class:`Manifest` into a :class:`CodegenSpec`.

    Implementation responsibilities:

    1. Pick a CLI name. If ``name`` is given, use it; otherwise derive from
       ``manifest.name`` (which sniff defaulted to the URL host) by lowercasing
       and replacing dots/dashes/underscores so it survives as a Python
       package slug.
    2. Compute ``base_url`` = scheme + host of ``manifest.source_url`` (no path).
    3. For each :class:`Endpoint`, produce a :class:`GeneratedCommand`:
       - command name: kebab-case of last meaningful URL-template segment
         + method suffix where method != GET; collisions get numeric suffixes.
       - path_params: extract ``{id}``, ``{uuid}``, etc. from the template.
       - query_params: parse the sample's request URL query string into
         ``{param: default}``; defaults from the sample become Typer option
         defaults (the user can override at runtime).
       - body_fields: if request_body_preview is JSON-shaped, flatten one
         level (top-level keys -> defaults). Otherwise mark body_is_raw.
       - headers: copy from the sample, dropping known-auth keys
         (Authorization, Cookie, X-Api-Key, X-Csrf-Token,
         Set-Cookie, Proxy-Authorization) unless ``keep_secrets`` is True.
       - description: terse one-liner from method + url_template.
    4. Assemble and return the CodegenSpec.

    TODO(query_params): the Manifest's :class:`EndpointSample` does not
    preserve the original recorded request URL, only normalized headers and
    body previews. Recovering per-endpoint query-param defaults would require
    threading the raw URL through HAR -> Manifest. For v1.0 we leave
    ``query_params={}``; runtime users still pass ``--name=value`` flags, just
    without sample-derived defaults.

    Pure function. No I/O. Deterministic for snapshot tests.
    """

    resolved_name = name if name else (manifest.name or "cli")
    pkg_slug = package_slug(resolved_name)

    parsed = urlparse(manifest.source_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    taken: set[str] = set()
    commands: list[GeneratedCommand] = []
    for endpoint in manifest.endpoints:
        cmd_name = command_name_from_endpoint(
            endpoint.method, endpoint.url_template, taken=taken
        )
        path_params = extract_path_params(endpoint.url_template)

        body_fields: dict[str, str] = {}
        body_is_raw = False
        request_headers: dict[str, str] = {}
        if endpoint.sample is not None:
            request_headers = endpoint.sample.request_headers
            preview = endpoint.sample.request_body_preview
            if preview is not None:
                stripped = preview.lstrip()
                if stripped.startswith("{"):
                    try:
                        parsed_body = json.loads(preview)
                    except (json.JSONDecodeError, ValueError):
                        body_is_raw = True
                    else:
                        if isinstance(parsed_body, dict):
                            for key, value in parsed_body.items():
                                if isinstance(value, str):
                                    body_fields[str(key)] = value
                                else:
                                    body_fields[str(key)] = json.dumps(value)
                        else:
                            body_is_raw = True
                else:
                    body_is_raw = True

        headers = sanitize_headers(request_headers, keep_secrets=keep_secrets)

        commands.append(
            GeneratedCommand(
                name=cmd_name,
                method=endpoint.method,
                url_template=endpoint.url_template,
                path_params=path_params,
                query_params={},
                body_fields=body_fields,
                body_is_raw=body_is_raw,
                headers=headers,
                description=f"{endpoint.method} {endpoint.url_template}",
            )
        )

    return CodegenSpec(
        name=resolved_name,
        package_slug=pkg_slug,
        source_url=manifest.source_url,
        base_url=base_url,
        user_agent=manifest.user_agent,
        keep_secrets=keep_secrets,
        commands=commands,
        schema_version=manifest.schema_version,
    )


def generate_all(
    spec: CodegenSpec,
    formats: list[str],
) -> list[GeneratedArtifact]:
    """Run the requested codegen modules and return every artifact they emit.

    ``formats`` is a list of strings, each one of: ``python_cli``,
    ``mcp_server``, ``claude_skill``, ``readme``. Unknown values raise
    :class:`ValueError`. Order in the returned list mirrors ``formats``.
    """

    artifacts: list[GeneratedArtifact] = []
    for fmt in formats:
        if fmt == "python_cli":
            from ghostpress.codegen import python_cli

            artifacts.extend(python_cli.generate(spec))
        elif fmt == "mcp_server":
            from ghostpress.codegen import mcp_server

            artifacts.extend(mcp_server.generate(spec))
        elif fmt == "claude_skill":
            from ghostpress.codegen import claude_skill

            artifacts.extend(claude_skill.generate(spec))
        elif fmt == "readme":
            from ghostpress.codegen import readme

            artifacts.extend(readme.generate(spec))
        else:
            raise ValueError(f"Unknown codegen format: {fmt}")
    return artifacts
