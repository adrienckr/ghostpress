"""Shared helpers for codegen modules: name slugging, param extraction, header sanitization."""

from __future__ import annotations

import re

__all__ = [
    "AUTH_HEADER_NAMES",
    "command_name_from_endpoint",
    "extract_path_params",
    "package_slug",
    "sanitize_headers",
    "slugify",
]

# Keep this lowercase — comparisons are case-insensitive.
AUTH_HEADER_NAMES: frozenset[str] = frozenset({
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "x-csrf",
    "x-xsrf-token",
    "x-amz-security-token",
    "proxy-authorization",
})

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_PATH_PARAM_RE = re.compile(r"\{([^}]+)\}")


def slugify(value: str) -> str:
    """kebab-case slug with [a-z0-9-] only. Empty input → empty string."""

    lowered = value.lower()
    collapsed = _SLUG_RE.sub("-", lowered)
    return collapsed.strip("-")


def package_slug(value: str) -> str:
    """Python-package-safe slug: lowercase, ``[a-z0-9_]``, no leading digit."""

    if not value:
        return "_"
    lowered = value.lower()
    collapsed = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if not collapsed:
        return "_"
    if collapsed[0].isdigit():
        collapsed = "_" + collapsed
    return collapsed


def command_name_from_endpoint(method: str, url_template: str, *, taken: set[str]) -> str:
    """Pick a unique kebab-case command name for an endpoint.

    Strategy:
    - Collapse the URL template to its last meaningful (non-placeholder) segment.
    - Append ``-<method>`` if method != GET.
    - If the result collides with ``taken``, append ``-1``, ``-2``, ...
    - Mutate ``taken`` so subsequent calls remain collision-free.
    """

    segments = [s for s in url_template.split("/") if s]
    last_meaningful = ""
    for segment in reversed(segments):
        if not (segment.startswith("{") and segment.endswith("}")):
            last_meaningful = segment
            break

    base = slugify(last_meaningful) or "root"
    if method.upper() != "GET":
        base = f"{base}-{method.lower()}"

    candidate = base
    counter = 1
    while candidate in taken:
        candidate = f"{base}-{counter}"
        counter += 1
    taken.add(candidate)
    return candidate


def extract_path_params(url_template: str) -> list[str]:
    """Return path-template placeholder names in order, e.g. ``['id', 'uuid']``."""

    return _PATH_PARAM_RE.findall(url_template)


def sanitize_headers(headers: dict[str, str], *, keep_secrets: bool) -> dict[str, str]:
    """Drop known-auth headers unless ``keep_secrets`` is True. Case-insensitive."""

    if keep_secrets:
        return dict(headers)
    return {
        name: value
        for name, value in headers.items()
        if name.lower() not in AUTH_HEADER_NAMES
    }
