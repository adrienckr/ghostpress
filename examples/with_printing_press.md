# ghostpress + printing-press

[printing-press](https://github.com/mvanhorn/cli-printing-press) generates a typed CLI and MCP server for any HTTP API given a HAR file. The catch: its built-in capture is HTTP-only, so anything sitting behind Cloudflare, Akamai, PerimeterX, or a JS-rendered SPA is invisible to it. ghostpress fills that gap by driving camoufox (a hardened Firefox fork) and dumping a real browser-grade HAR that printing-press can consume verbatim.

## Prerequisites

- ghostpress installed (`pip install ghostpress`) and `python -m camoufox fetch` already run.
- printing-press on your `PATH`:

```bash
go install github.com/mvanhorn/cli-printing-press/v4/cmd/printing-press@latest
```

## Step 1 — capture

```bash
ghostpress sniff https://target.example.com \
  --out ./capture \
  --duration 30 \
  --name target
```

Expected output:

```
sniff complete
  HAR:        ./capture/har.json
  Manifest:   ./capture/manifest.json
  Endpoints:  17
```

If a captcha challenge fires during the window, ghostpress flags it on stderr (`Captcha detected: cf-chl`) so you know the capture is incomplete and should be retried with `--headed --interact`.

## Step 2 — generate

Hand the HAR to printing-press:

```bash
printing-press --har ./capture/har.json --name target
```

This produces two artifacts in the current directory:

- `target-pp-cli` — a typed CLI mirroring every endpoint observed.
- `target-pp-mcp` — an MCP server exposing the same surface to any MCP-aware agent.

## Step 3 — verify

```bash
target-pp-cli --help
```

You should see one subcommand per distinct endpoint printing-press inferred from the HAR.

## When to use --headed

Some sites gate their interesting API surface behind an interactive sign-in, a cookie banner, or a multi-step form. Headless capture in that case yields a HAR full of static asset GETs and nothing else. Switch to:

```bash
ghostpress sniff https://target.example.com \
  --out ./capture \
  --headed \
  --interact \
  --duration 120
```

The window stays open for the full duration; sign in, click through whatever the operator flow requires, and ghostpress records every request the browser issues during that window.

## Why this works

camoufox ships with anti-fingerprinting patches that make Firefox's TLS handshake, navigator surface, and font enumeration match a regular browser rather than a stock Playwright build. Most bot-protection vendors gate on those signals first, so the page renders and the real API calls leave the browser intact. The HAR ghostpress writes is a faithful record of those calls — printing-press treats it as ground truth and never has to negotiate the protection layer itself.

---

See [responsible use](../RESPONSIBLE_USE.md) before pointing this at anything you do not own.
