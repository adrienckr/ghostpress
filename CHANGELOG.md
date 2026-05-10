# Changelog

All notable changes to this project will be documented in this file. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
- `RESPONSIBLE_USE.md` enumerating intended-use scope.

### Pinned

- `camoufox[geoip] >=0.4.0,<0.5.0` (stable line; alpha `0.5.x` tracked
  separately).
- `mcp >=1.0.0,<2.0.0`.
