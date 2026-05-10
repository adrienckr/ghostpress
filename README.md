# ghostpress

**URL → CLI in 60 seconds.** Stealth-browser sniff + codegen — works on Amazon, Cloudflare, anything else.

[![ci](https://github.com/adrienckr/ghostpress/actions/workflows/ci.yml/badge.svg)](https://github.com/adrienckr/ghostpress/actions/workflows/ci.yml)
[![pypi](https://img.shields.io/pypi/v/ghostpress.svg)](https://pypi.org/project/ghostpress/)
[![python](https://img.shields.io/pypi/pyversions/ghostpress.svg)](https://pypi.org/project/ghostpress/)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## The pitch

There are great codegen tools for the "URL or HAR -> typed CLI" job. [printing-press](https://printingpress.dev) is the best of them — it turns an API spec or a HAR file into a Go CLI, an MCP server, and a Claude Code skill, with a SQLite mirror and agent-native compound commands. It is the bar to clear. But every tool in this category dies on the same wall: bot detection. Amazon. Cloudflare-walled SaaS dashboards. JS-heavy SPAs that fingerprint navigator, canvas, WebGL, and TLS before they let a single XHR through. The capture step is where the dream breaks. The HAR comes back full of static assets and the generated CLI is empty.

`ghostpress` drops [camoufox](https://github.com/daijro/camoufox) — a C++-patched stealth Firefox build with anti-fingerprinting baked in — into the capture step. Same paradigm: sniff -> manifest -> CLI. Same MCP-friendly output. The wall is gone.

## What you get

```bash
pip install ghostpress
python -m camoufox fetch
ghostpress build https://www.amazon.com/product-reviews/<ASIN>
# 60s later:
out/amazon-com/cli.py reviews
out/amazon-com/mcp.py     # also an MCP server
out/amazon-com/skill.md   # also a Claude Code skill
```

What `ghostpress build` actually does:

- Launches a stealth Firefox session (camoufox).
- Captures every API call the page makes during the observation window.
- Converts the capture into a printing-press v4-compatible manifest.
- Generates a standalone Typer CLI, an MCP server, and a Claude Code skill.
- Drops everything in `out/<name>/` with a per-CLI README.

## Prompt mode

You don't have to know the URL. Describe what you want and let Claude pick.

```bash
export ANTHROPIC_API_KEY=...
ghostpress build --prompt "I want a CLI for the Hacker News API"
# -> Claude proposes URLs, you confirm, build runs end-to-end.
```

## CLI reference

| Command | Purpose |
| --- | --- |
| `ghostpress build <url>` | URL -> CLI in 60 seconds. The headline command. Sniffs, generates, writes everything to `out/<name>/`. |
| `ghostpress build --prompt "..."` | Natural-language description; ghostpress picks the URL via Claude Opus 4.7. |
| `ghostpress sniff <url>` | One-shot stealth capture. Writes `har.json` + `manifest.json` to `--out`. No codegen. |
| `ghostpress mcp` | Start the MCP server on stdio. Used as the launch command in `claude mcp add` / Cursor / any stdio MCP client. |
| `ghostpress run <flow.yaml>` | Execute a multi-step browser flow declared in YAML (login, click, then sniff). |
| `ghostpress gallery` | List bundled example CLIs from `examples/gallery/`. |

Common flags on `build` and `sniff`: `--out`, `--duration`, `--name`, `--headed`, `--proxy`. Build adds `--prompt`, `--keep-secrets`, and `--formats` (default `python_cli,mcp_server,claude_skill,readme`). Sniff adds `--interact` for operator-driven captures.

## MCP tools

The `ghostpress mcp` server exposes nine stealth-browser tools, useful as a power-user surface even when you're not running a build.

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

A single `SessionRegistry` lives for the connection's lifetime, so a session opened in one tool call survives across the next call from the same client.

## Architecture

```
URL ──► camoufox session ──► HAR ──► Manifest ──► CodegenSpec ──┬─► Python CLI (Typer + httpx)
                                                                ├─► MCP server (stdio)
                                                                ├─► Claude Code skill
                                                                └─► per-CLI README
```

The `CodegenSpec` is a pure deterministic projection of the manifest — see [docs/codegen_format.md](docs/codegen_format.md) for the contract and snapshot-test guarantees.

## vs printing-press

| | printing-press | ghostpress |
| --- | --- | --- |
| Source | OpenAPI spec, URL, HAR file | URL, prompt, HAR file |
| Capture | plain HTTP | stealth Firefox (camoufox) |
| Bot-protected sites | empty CLI | works |
| Output language | Go | Python (Typer) |
| Caching layer | local SQLite mirror | none (v1.0) |
| Pre-built gallery | 60+ community CLIs | small starter set |

ghostpress and printing-press are not in conflict — `ghostpress sniff` writes a printing-press v4 manifest, so you can use ghostpress purely as the capture front-end if you prefer printing-press's Go output and SQLite caching. Long version: [docs/positioning.md](docs/positioning.md).

## Examples gallery

Pre-built CLIs you can run without doing your own capture: [examples/gallery/](examples/gallery/). Coming soon — Hacker News, GitHub public, httpbin. In the meantime, [examples/flows/](examples/flows/) has runnable YAML flows for `ghostpress run`.

## Limits

The honesty section.

- Generated CLIs are good defaults, not production-ready clients. Auth flows beyond cookie replay (OAuth, signed requests) need manual edits.
- Pagination needs operator hints. The generator will not infer cursor structures from a single sample.
- Rate limiting is the operator's responsibility. Don't point the generated CLI at someone else's infrastructure and run a tight loop.
- Captcha walls are detected and surfaced (`captcha_detected: true` in the build result), not solved. ghostpress will not bundle a bypass.
- `--keep-secrets` replays the captured `Authorization` / `Cookie` / `X-Api-Key` headers verbatim into the generated code. Off by default for a reason.

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

## Roadmap (v1.1+)

- Distributed sniff: shard a target list across worker processes with a shared output bucket.
- Captcha solver hooks: pluggable resolver interface (operator-supplied, no bundled bypass).
- Residential proxy pool: round-robin selection with sticky sessions per target.
- Web playground: paste a URL in a browser, get a downloadable CLI.
- OAuth flow generation: detect login redirects in the capture and emit a working token-refresh path.

## License

MIT — see [LICENSE](LICENSE).
