# Changelog

All notable changes to this project will be documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-05-09

### Added

- `ghostpress build <url>` — the headline command. Runs `sniff` then fans out
  through codegen to emit a standalone Python CLI (Typer + httpx), an MCP
  server, a Claude Code skill, and a per-CLI README — all under `out/<name>/`.
- `ghostpress build --prompt "<goal>"` — natural-language description; Claude
  Opus 4.7 proposes 1-3 candidate URLs (cached for 24h), the first is selected,
  the standard build runs end-to-end. Requires `ANTHROPIC_API_KEY`.
- `ghostpress gallery` — list bundled example CLIs in `examples/gallery/`.
- `ghostpress.codegen` package: pure deterministic projection
  (`spec_from_manifest`) plus four format-specific generators
  (`python_cli`, `mcp_server`, `claude_skill`, `readme`). Templates live at
  `src/ghostpress/templates/*.jinja` — fork-and-edit friendly.
- Auth-header redaction by default; `--keep-secrets` opt-in for replay.
- Snapshot-tested codegen (92 new tests; 201 total).
- `docs/positioning.md`, `docs/codegen_format.md`, `docs/prompt_mode.md`.
- Full README rewrite around URL → CLI in 60 seconds.
- `DEMO.md` + private `launch/` drafts (Reddit / HN / Tweet) — gitignored
  until launch day.

### Pinned

- `jinja2 >=3.1.0` (template rendering).
- `anthropic >=0.40.0` (prompt mode; lazy-imported only when used).

## [0.1.0] — 2026-05-09

### Added

- `ghostpress sniff <url>` — drives a camoufox stealth Firefox session, captures
  network traffic during a configurable observation window, and writes both a
  HAR file and a printing-press-compatible endpoint manifest.
- `ghostpress mcp` — an MCP server exposing stealth-browser tools
  (`stealth_navigate`, `stealth_click`, `stealth_fill`, `stealth_read_page`,
  `stealth_screenshot`, `stealth_capture_har`, `stealth_export_manifest`,
  `stealth_session_open`, `stealth_session_close`) over stdio.
- `ghostpress run <flow.yaml>` — execute a multi-step browser flow declared in
  YAML.
- Integration recipe with printing-press: `printing-press --har <ghostpress
  output> --name X` works against bot-protected sites.

### Pinned

- `camoufox[geoip] >=0.4.0,<0.5.0` (stable line; alpha `0.5.x` tracked
  separately).
- `mcp >=1.0.0,<2.0.0`.
