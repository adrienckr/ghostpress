"""Tests for ``ghostpress.codegen`` (spec_from_manifest, generate_all)."""

from __future__ import annotations

import keyword
from pathlib import Path

import pytest

from ghostpress._types import HAR, GeneratedArtifact, Manifest
from ghostpress.codegen import generate_all, spec_from_manifest
from ghostpress.manifest import har_to_manifest


def _manifest_from_sample(sample_har: HAR) -> Manifest:
    return har_to_manifest(
        sample_har,
        name="api.example.com",
        source_url="https://api.example.com/",
        capture_time="2026-05-09T12:00:00Z",
        user_agent="ghostpress-test/0.1",
    )


def test_spec_command_count_matches_manifest_endpoints(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest)
    assert len(spec.commands) == len(manifest.endpoints)


def test_spec_package_slug_is_import_safe(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest)
    slug = spec.package_slug
    assert slug.isidentifier()
    assert not keyword.iskeyword(slug)


def test_spec_command_names_are_unique(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest)
    names = [c.name for c in spec.commands]
    assert len(names) == len(set(names))


def test_spec_explicit_name_overrides_manifest(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest, name="amazon-reviews")
    assert spec.name == "amazon-reviews"


def test_spec_explicit_name_yields_safe_package_slug(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest, name="amazon-reviews")
    assert spec.package_slug == "amazon_reviews"


def test_spec_keep_secrets_true_retains_authorization(manifest_v1_path: Path) -> None:
    manifest = Manifest.model_validate_json(manifest_v1_path.read_text())
    spec = spec_from_manifest(manifest, keep_secrets=True)
    auth_cmds = [
        c for c in spec.commands if "authorization" in {k.lower() for k in c.headers}
    ]
    assert auth_cmds


def test_spec_keep_secrets_false_drops_authorization(manifest_v1_path: Path) -> None:
    manifest = Manifest.model_validate_json(manifest_v1_path.read_text())
    spec = spec_from_manifest(manifest, keep_secrets=False)
    for cmd in spec.commands:
        lowered = {k.lower() for k in cmd.headers}
        assert "authorization" not in lowered


def test_generate_all_returns_artifacts_for_all_formats(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest)
    artifacts = generate_all(
        spec, ["python_cli", "mcp_server", "claude_skill", "readme"]
    )
    assert all(isinstance(a, GeneratedArtifact) for a in artifacts)


def test_generate_all_artifact_paths(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest)
    artifacts = generate_all(
        spec, ["python_cli", "mcp_server", "claude_skill", "readme"]
    )
    paths = {a.path for a in artifacts}
    assert {"cli.py", "pyproject.toml", "mcp.py", "skill.md", "README.md"} <= paths


def test_generate_all_empty_formats_returns_empty(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest)
    assert generate_all(spec, []) == []


def test_generate_all_unknown_format_raises(sample_har: HAR) -> None:
    manifest = _manifest_from_sample(sample_har)
    spec = spec_from_manifest(manifest)
    with pytest.raises(ValueError):
        generate_all(spec, ["nope"])
