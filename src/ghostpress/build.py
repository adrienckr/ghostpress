"""``ghostpress build`` orchestrator.

The full pipeline: sniff (camoufox) -> manifest -> CodegenSpec -> fan-out codegen
-> write artifacts to ``out_dir/<name>/``. Returns a :class:`BuildResult`.

This is the v1.0 product surface. Most users never call ``sniff`` directly.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from ghostpress._types import (
    BuildOptions,
    BuildResult,
    Manifest,
    SniffOptions,
)

__all__ = ["build"]


def _slugify_host(host: str) -> str:
    """Lower-case the host and replace non-alphanumeric runs with hyphens."""

    lowered = host.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "cli"


async def build(options: BuildOptions) -> BuildResult:
    """Run sniff -> codegen end-to-end."""

    start = time.monotonic()

    if options.name:
        name = options.name
    else:
        parsed = urlparse(options.url)
        host = parsed.hostname or options.url
        name = _slugify_host(host)

    per_cli_dir = Path(options.out_dir) / name
    per_cli_dir.mkdir(parents=True, exist_ok=True)

    sniff_opts = SniffOptions(
        url=options.url,
        out_dir=str(per_cli_dir),
        duration_seconds=options.duration_seconds,
        name=name,
        profile=options.profile,
        proxy=options.proxy,
        interact=options.interact,
    )

    from ghostpress.sniff import sniff

    sniff_result = await sniff(sniff_opts)

    manifest = Manifest.model_validate_json(
        Path(sniff_result.manifest_path).read_text()
    )

    from ghostpress.codegen import generate_all, spec_from_manifest

    spec = spec_from_manifest(
        manifest, name=name, keep_secrets=options.keep_secrets
    )

    try:
        artifacts = generate_all(spec, options.formats)
    except Exception as e:
        raise RuntimeError(f"codegen failed: {e}") from e

    for artifact in artifacts:
        path = per_cli_dir / artifact.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(artifact.content)
        if artifact.executable:
            os.chmod(path, 0o755)

    elapsed = time.monotonic() - start

    return BuildResult(
        out_dir=str(per_cli_dir),
        har_path=sniff_result.har_path,
        manifest_path=sniff_result.manifest_path,
        artifacts=[a.path for a in artifacts],
        command_count=len(spec.commands),
        captcha_detected=sniff_result.captcha_detected,
        captcha_signal=sniff_result.captcha_signal,
        elapsed_seconds=elapsed,
    )
