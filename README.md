# ghostpress

Stealth-browser sniff daemon for printing-press — capture APIs from bot-protected sites.

[![ci](https://github.com/adrienckr/ghostpress/actions/workflows/ci.yml/badge.svg)](https://github.com/adrienckr/ghostpress/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/ghostpress.svg)](https://pypi.org/project/ghostpress/)
[![python](https://img.shields.io/pypi/pyversions/ghostpress.svg)](https://pypi.org/project/ghostpress/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[printing-press](https://github.com/mvanhorn/cli-printing-press) takes a HAR file and synthesises a typed CLI plus an MCP server for any HTTP API. It works beautifully against open APIs, but its built-in capture path is plain HTTP — anything sitting behind Cloudflare, Akamai, PerimeterX, hCaptcha, Turnstile, or a single-page app that fingerprints navigator/canvas/WebGL is invisible to it. The HAR comes back full of static assets and the generated CLI is empty.

`ghostpress` fills that gap. It drives [camoufox](https://github.com/daijro/camoufox) — a hardened Firefox fork with anti-fingerprinting patches — against the target, records the network conversation, and emits a HAR plus a printing-press v4 manifest that printing-press consumes verbatim. The same surface is exposed over MCP so Claude Code, Cursor, or any other MCP client can drive a stealth browser as a first-class tool.

## What you can do

- Capture HARs from sites that gate on TLS, navigator, canvas, WebGL, or font fingerprinting.
- Hand the HAR to `printing-press` and get a generated typed CLI and MCP server for the target.
- Drive a stealth browser from Claude Code (or any MCP client) through 9 tools.
- Script multi-step flows (login, click-through, then sniff) declaratively in YAML.

## Install

```bash
pip install ghostpress
python -m camoufox fetch
```

`python -m camoufox fetch` downloads the patched Firefox build (~250 MB) into camoufox's cache. Running it explicitly avoids surprising download stalls on the first sniff.

## Quickstart

### 1. Sniff a HAR

```bash
ghostpress sniff https://news.ycombinator.com --out ./capture --duration 10
```

Expected output:

```
sniff complete
  HAR:        ./capture/har.json
  Manifest:   ./capture/manifest.json
  Endpoints:  4
```

### 2. Use it with printing-press

```bash
printing-press --har ./capture/har.json --name HN
```

`printing-press` reads the HAR, validates `schema_version=1` on the manifest, and generates `HN-pp-cli` plus `HN-pp-mcp` in the current directory.

### 3. Register as an MCP server in Claude Code

```bash
claude mcp add ghostpress -- ghostpress mcp
```

The `mcp` subcommand starts an stdio MCP server with all 9 stealth tools. A single `SessionRegistry` lives for the connection's lifetime, so a session opened in one tool call survives across the next call from the same client.

## CLI reference

`ghostpress` exposes three subcommands.

### `ghostpress sniff <url>`

| Flag | Default | Purpose |
| --- | --- | --- |
| `--out`, `-o` | `./capture` | Output directory (created if missing). |
| `--duration`, `-d` | `30.0` | Seconds to observe the page after `domcontentloaded`. |
| `--name`, `-n` | host of URL | Manifest `name` field. |
| `--headed` | `False` | Run with a visible browser window. |
| `--proxy` | none | Proxy URL (`scheme://user:pass@host:port`). |
| `--interact` | `False` | Keep the window open for operator clicks during the capture window. |

### `ghostpress mcp`

Starts the MCP server on stdio. No flags. Used as the launch command in `claude mcp add` / Cursor MCP config / any stdio MCP client.

### `ghostpress run <flow.yaml>`

| Flag | Default | Purpose |
| --- | --- | --- |
| `--out`, `-o` | `./runs` | Output directory for run evidence (per-step JSON artifacts). |

Each step in the flow writes a JSON artifact under `<out>/runs/<run-id>/<NN>_<action>.json` so every execution is auditable.

## MCP tools

| Tool | Description |
| --- | --- |
| `stealth_session_open` | Open a stealth camoufox session and return a `session_id`. |
| `stealth_session_close` | Close a previously opened stealth session. |
| `stealth_navigate` | Navigate the session to a URL. |
| `stealth_click` | Click the first element matching a CSS selector. |
| `stealth_fill` | Type text into an input matching a CSS selector. |
| `stealth_read_page` | Return the current page as a markdown digest. |
| `stealth_screenshot` | Capture a PNG screenshot, base64-encoded. |
| `stealth_capture_har` | Capture network events for a duration and return a HAR. |
| `stealth_export_manifest` | Convert a HAR JSON string into a printing-press manifest. |

Schemas live in [`ghostpress.mcp_server._TOOL_DEFS`](src/ghostpress/mcp_server.py).

## Architecture

`ghostpress` is a thin async core. Both the CLI and the MCP server delegate to the same tool functions, which in turn share a `SessionRegistry` that owns the underlying camoufox processes.

```
  ghostpress sniff ──┐
  ghostpress run ────┼──► SessionRegistry ──► camoufox (Firefox + anti-fp) ──► target
  ghostpress mcp ────┘                                │
                                                       └─► HAR ──► Manifest (printing-press v4)
```

See [docs/architecture.md](docs/architecture.md) for the module map and design decisions.

## Examples

- [docs/quickstart.md](docs/quickstart.md) — first sniff, common flags, and troubleshooting.
- [examples/with_printing_press.md](examples/with_printing_press.md) — end-to-end recipe pairing ghostpress with printing-press, including the `--headed --interact` flow for sites behind interactive logins.
- [examples/flows/](examples/flows/) — sample YAML flows you can hand to `ghostpress run`.

## Development

```bash
git clone https://github.com/adrienckr/ghostpress
cd ghostpress
pip install -e ".[dev]"
python -m camoufox fetch
pytest
ruff check .
pyright src/
```

Integration tests (real browser, real network) are gated behind the `integration` pytest marker and skipped by default. Run them with `pytest -m integration` once `python -m camoufox fetch` has completed.

## Roadmap (v0.2+)

- Distributed sniff: shard a target list across worker processes with a shared output bucket.
- Captcha solver hooks: pluggable resolver interface (operator-supplied, no bundled bypass).
- Residential proxy pool: round-robin selection with sticky sessions per target.
- Alpha camoufox track: optional pin against `0.5.x` for early access to upstream fingerprint patches.

## License

MIT — see [LICENSE](LICENSE).
