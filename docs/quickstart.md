# Quickstart

`ghostpress` drives a stealth Firefox build (camoufox) against a target URL,
records the network conversation as a HAR, and converts it into a manifest
that printing-press consumes directly. This page walks through installation,
a first sniff, and the three ways to drive ghostpress: one-shot CLI, MCP
server, and YAML flows.

## Prerequisites

- Python 3.11 or newer.
- About 10 GB of free disk for the camoufox binary and its bundled GeoIP data
  (downloaded once on first use).
- Roughly 500 MB of RAM headroom per concurrent session. The default
  `--parallel 1` keeps a single browser instance alive at a time.
- Network access for the camoufox download (cached afterwards).

## Install

```bash
pip install ghostpress
python -m camoufox fetch
```

The second command pulls the patched Firefox build into camoufox's cache.
Running it explicitly avoids surprising download stalls on the first sniff
and makes errors easier to diagnose.

## First sniff

Pick a benign target. Hacker News is a reliable smoke test because it does
not gate on bot challenges and serves a small JSON-bearing surface.

```bash
ghostpress sniff https://news.ycombinator.com --out ./capture --duration 10
```

Expected output (counts will vary):

```
sniff complete
  HAR:        ./capture/har.json
  Manifest:   ./capture/manifest.json
  Endpoints:  4
```

Inside `./capture` you will find:

- `har.json` — full HTTP Archive 1.2 transcript of the session.
- `manifest.json` — printing-press v4 manifest with one entry per endpoint.

If the target serves a Cloudflare or hCaptcha challenge during the window,
ghostpress detects it and reports a warning line. It does not attempt to
solve the challenge — see [RESPONSIBLE_USE.md](../RESPONSIBLE_USE.md).

## Use it with printing-press

The manifest produced above feeds straight into printing-press:

```bash
printing-press --har ./capture/har.json --name HN
```

printing-press reads the HAR file, validates the manifest's
`schema_version=1`, and generates a typed client. The internal contract is
documented in [manifest format](manifest_format.md).

## Use it as an MCP server

ghostpress exposes the same stealth-browser surface as an MCP server over
stdio. Register it once in Claude Code and the tools become available across
sessions:

```bash
claude mcp add ghostpress -- ghostpress mcp
```

The `ghostpress` binary is the package's `[project.scripts]` entry point;
the `mcp` subcommand starts the stdio server defined in
`ghostpress.mcp_server.run_stdio`. Tools exposed:

- `stealth_session_open` / `stealth_session_close`
- `stealth_navigate`, `stealth_click`, `stealth_fill`
- `stealth_read_page`, `stealth_screenshot`
- `stealth_capture_har`, `stealth_export_manifest`

Schemas live in `ghostpress.mcp_server._TOOL_DEFS`. The MCP server keeps a
single `SessionRegistry` for the connection's lifetime, so a session opened
in one tool call survives across the next call from the same client.

## Run a multi-step flow

For repeatable captures (login, click, then sniff) use a YAML flow and the
`run` subcommand:

```yaml
name: hn-front-page
steps:
  - action: navigate
    args: { url: https://news.ycombinator.com }
  - action: capture_har
    args: { duration_seconds: 10 }
```

```bash
ghostpress run flow.yaml --out ./runs
```

Each step writes a JSON artifact into `./runs/runs/<id>/<NN>_<action>.json`,
so the trail of every flow is auditable. Available actions are listed in the
`FlowAction` literal in `ghostpress._types`.

## Common flags

`ghostpress sniff` accepts:

| Flag | Default | Purpose |
| --- | --- | --- |
| `--out`, `-o` | `./capture` | Output directory. Created if missing. |
| `--duration`, `-d` | `30.0` | Seconds to leave the browser idle on the page after `domcontentloaded`. |
| `--name`, `-n` | host of URL | Manifest `name` field. Pick a stable identifier per target. |
| `--headed` | `False` | Show the browser window. Useful when troubleshooting selectors or interactive logins. |
| `--proxy` | none | Proxy URL in `scheme://user:pass@host:port` form. Forwarded to camoufox so its bundled GeoIP picks the matching locale/timezone. |
| `--interact` | `False` | Keep the window open so the operator can click through a challenge or dismiss a modal before the capture window expires. Implies `--headed` in practice. |

## Troubleshooting

**camoufox download failed.** Run `python -m camoufox fetch` separately. The
download is large and pulls from GitHub releases; corporate proxies and
captive networks routinely interrupt it. Retrying the standalone fetch
gives clearer error output than the embedded launch path.

**captcha detected.** ghostpress reports the signal it saw (`hcaptcha`,
`recaptcha`, `turnstile`, `cloudflare`) and writes whatever HAR it managed to
capture before the wall. ghostpress does not attempt to solve interactive
challenges. See [RESPONSIBLE_USE.md](../RESPONSIBLE_USE.md) for the project's
position on bypassing access controls.

**zero endpoints in the manifest.** The HAR → manifest converter only keeps
JSON and form-encoded responses. If the target serves only HTML and static
assets, `manifest.json` will have an empty `endpoints` array. Increase
`--duration` to give XHR/fetch traffic time to fire, or trigger interactions
yourself with `--interact`.

**camoufox launch failed.** Wrapped errors come back as `RuntimeError:
camoufox launch failed: <reason>`. The most common reasons are a missing
binary (run `python -m camoufox fetch`), insufficient RAM (close other
browser instances), or a proxy URL the upstream cannot reach.

## Where to go next

- [architecture.md](architecture.md) — module map and the design decisions
  that shape the public surface.
- [manifest format](manifest_format.md) — the manifest schema and the rules
  the converter applies.
- [RESPONSIBLE_USE.md](../RESPONSIBLE_USE.md) — what ghostpress is and is not
  meant to be used for.
