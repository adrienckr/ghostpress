# Architecture

`ghostpress` exists to bridge two tools that do not talk to each other.
[printing-press](https://github.com/) generates typed API clients from HAR
files, but it cannot itself navigate sites that gate on bot detection.
[camoufox](https://github.com/daijro/camoufox) is a stealth Firefox build
that bypasses passive fingerprinting at the C++ level, but it does not emit
printing-press's manifest format. ghostpress drives camoufox, captures the
network conversation, and converts it into the exact shape printing-press
expects.

This document covers the system shape, module responsibilities, and the
decisions that pinned the public surface in v0.1.

## System diagram

```
              CLI (sniff / run / mcp)              MCP client
                       |                                |
                       v                                v
               +------------------+         +----------------------+
               |   cli.py / mcp_  |         |  mcp_server.run_stdio|
               |   server.py      |--------->                      |
               +--------+---------+         +----------+-----------+
                        |                              |
                        v                              v
                  +-----+------------------------------+-----+
                  |        SessionRegistry (tools.py)        |
                  |  - process-local                          |
                  |  - one-per-MCP-connection                 |
                  +-----+------------------------------+-----+
                        |
                        v
              +-------------------+         +-------------------+
              |  AsyncCamoufox    |-------->|  patched Firefox  |
              |  (camoufox.async) |         |  binary           |
              +---------+---------+         +---------+---------+
                        |                             |
                        |  page.on(request/response)  |
                        v                             v
              +-------------------+        +---------------------+
              |  event capture    |        |   target site       |
              |  (sniff.py)       |<-------+   (HTTPS, JS-heavy) |
              +---------+---------+        +---------------------+
                        |
                        v
              +-------------------+
              | build_har_from_   |
              | events()          |
              +---------+---------+
                        |
                        v
              +-------------------+
              | har_to_manifest() |--->  manifest.json (printing-press v4)
              | (manifest.py)     |
              +-------------------+
                        |
                        v
              +-------------------+
              |  printing-press   |
              |  --har / --name   |
              +-------------------+
```

The arrows are blocking calls. The dashed contract between ghostpress and
printing-press is the manifest format, pinned in
`tests/fixtures/manifest_v1.json`.

## Module-by-module

### `sniff`

`ghostpress.sniff` is the one-shot capture path. `sniff(options)` launches
`AsyncCamoufox`, attaches request/response/requestfailed listeners to the
page, navigates, idles for `options.duration_seconds`, and writes
`har.json` + `manifest.json`. It also runs a captcha probe (DOM selector
plus title-string heuristic) and surfaces the signal on `SniffResult`. The
event-to-HAR conversion is split out into `build_har_from_events` so unit
tests can exercise it without booting a real browser.

### `manifest`

`ghostpress.manifest.har_to_manifest` is the conversion that gives
ghostpress its reason to exist: HAR in, printing-press-shaped manifest out.
`extract_endpoints` does the grouping (filter by MIME type, group by
`(method, url_template)`, pick the first 200-OK as sample). `url_to_template`
collapses query strings, numeric segments, and UUIDs into placeholders.
The conversion is deterministic — same input HAR yields the same manifest
bytes — because downstream printing-press code generation is reproducible
only if the manifest is stable.

### `tools`

`ghostpress.tools` is the action surface shared by the MCP server and the
flow runner. Each `stealth_*` function returns a typed `ToolResult` subclass
and never raises across the API boundary; failures land in the
`ok=False / error=...` envelope. The module also defines `SessionRegistry`,
the in-process map of session ids to `(camoufox context manager, browser,
page)` tuples. Splitting the tools out of `mcp_server.py` keeps the MCP
wiring trivially thin and lets the YAML flow runner reuse the same
implementations.

### `fingerprint`

`ghostpress.fingerprint.profile_to_camoufox_kwargs` translates a
high-level `BrowserProfile` (headless, locale, timezone, viewport, geoip
toggle, user-data dir) into the kwargs `AsyncCamoufox` actually accepts.
The intent is to keep ghostpress's user-facing struct tidy while letting
camoufox own the heavy fingerprint generation through BrowserForge. The
module is intentionally thin and `default_profile()` returns the
"headless, geoip on" baseline used by `ghostpress sniff` when no flags
are passed.

### `proxy`

`ghostpress.proxy.proxy_to_playwright_dict` serializes a `ProxyConfig` to
the dict shape camoufox expects (which mirrors Playwright's spec).
`parse_proxy_url` splits embedded credentials out of the URL so we can
hand camoufox a credential-less server URL plus separate `username` /
`password` fields. The split matters because some proxies reject
credentials embedded in the URL despite RFC 3986 allowing them.

### `mcp_server`

`ghostpress.mcp_server.build_server` registers the nine `stealth_*` tools
(see schemas in `_TOOL_DEFS`) on an MCP `Server` and binds them to a
single shared `SessionRegistry`. `run_stdio` runs the server on stdio,
which is the contract `claude mcp add ghostpress -- ghostpress mcp`
expects. The registry is intentionally not multiplexed across concurrent
clients — see "Concurrency model" below for why.

### `cli`

`ghostpress.cli` is a Typer app with three subcommands. `sniff` calls
`ghostpress.sniff.sniff` directly. `mcp` delegates to
`mcp_server.run_stdio`. `run` parses a YAML flow into the `Flow` Pydantic
model and dispatches each step to the matching `stealth_*` function via
`SessionRegistry`. Every step writes its `ToolResult` JSON to
`./runs/runs/<id>/<NN>_<action>.json` for auditability.

### `_types`

`ghostpress._types` is the Pydantic schema layer. It defines the HAR types
(`HAR`, `HARLog`, `HAREntry`, `HARRequest`, `HARResponse`), the manifest
types (`Manifest`, `Endpoint`, `EndpointSample`), the operator-facing
configs (`BrowserProfile`, `ProxyConfig`, `SniffOptions`), the flow types
(`Flow`, `FlowStep`, `FlowAction`), and the typed `ToolResult` envelopes
the MCP server returns. The module is private (the leading underscore is
deliberate) because public consumers should import from `ghostpress`,
which re-exports the supported names.

## Concurrency model

`SessionRegistry` is **process-local**. One ghostpress process owns one
registry. The MCP server constructs exactly one registry in
`build_server` and threads it through every tool call for the connection's
lifetime — when the stdio connection drops, `run_stdio` calls
`registry.aclose()` and the camoufox subprocesses are torn down.

We intentionally do not share sessions across MCP clients. Two reasons:

- **State isolation.** A session carries cookies, localStorage, and the
  browser's network principal store. Sharing it across agents would leak
  one agent's authenticated state into another's tool calls.
- **Privacy.** Even within a single user, two parallel flows usually
  represent unrelated work. Crossing their state hides bugs that would be
  obvious if each flow had its own session.

If you want concurrent captures, run multiple `ghostpress sniff` processes.
Each gets its own registry and its own camoufox instance.

## Why camoufox

Standard Playwright Chromium bots are detectable through a long list of
passive signals. camoufox patches Firefox at the C++ level so the
fingerprint matches a real browser instead of a Selenium-style automation
shell. Specifically, camoufox addresses:

- **TLS fingerprint** — JA3/JA4 ordering matches stock Firefox.
- **`navigator` properties** — `navigator.webdriver`, `navigator.plugins`,
  `navigator.languages`, `navigator.platform` all return values consistent
  with the rendered fingerprint.
- **Canvas** — 2D canvas readback is noised in a deterministic way per
  fingerprint so it does not match a known automation profile.
- **WebGL** — `RENDERER` and `VENDOR` strings come from BrowserForge's
  fingerprint pool instead of Mesa/SwiftShader.
- **WebRTC** — local IP leaks are suppressed; STUN behaviour matches a
  consumer connection.
- **Fonts** — the font fingerprint is consistent with the OS implied by
  the chosen fingerprint.
- **Headless detection** — the headless-mode signals (window dimensions,
  permission prompts, missing properties) are masked.

What camoufox does **not** do:

- It does not solve interactive captchas (hCaptcha, reCAPTCHA, Turnstile,
  Cloudflare's interactive challenge). When ghostpress sees those, it
  records the signal and stops.
- It does not rotate IPs. If you need a residential proxy pool, plug it
  in via `--proxy`.
- It does not defeat behavioural detection (mouse-movement entropy,
  timing-based scoring). Treat the session as low-volume and human-paced.

## Why a printing-press-compatible manifest

printing-press v4 expects a very specific JSON shape: `schema_version`,
flat `endpoints` list, each endpoint with `method` / `url_template` /
`response_content_type` / `request_count` / `sample`. ghostpress emits
exactly that shape so `printing-press --har <ghostpress output> --name X`
works without an adapter step.

The contract is enforced by a fixture-driven CI guard. The canonical
output is `tests/fixtures/manifest_v1.json`; any drift in
`har_to_manifest` against that fixture fails the test suite. See
[manifest format](manifest_format.md) for the full schema.

## Resource budget

camoufox's docs put a single browser instance at roughly **200 MB RSS**.
ghostpress allocates one instance per active session, so:

- `ghostpress sniff` uses ~200 MB while the capture window is open and
  releases on exit.
- A long-lived MCP connection with one session open holds ~200 MB until
  the client disconnects.
- A flow with one session uses ~200 MB; the runner closes the session in
  its `finally` block.

The default `--parallel 1` reflects that budget. Raising it linearly
multiplies RAM use; do it deliberately and monitor.

## Limits and follow-ups

Things that exist as v0.2 candidates but did not ship in v0.1:

- **Distributed sniff.** Multiple sniffs against the same target
  coordinated through a shared queue, with output merged into a single
  manifest.
- **Captcha solver hooks.** A pluggable interface that hands an
  interactive challenge off to an external solver. Out of scope for v0.1.
- **Residential proxy pool.** First-class integration with rotating
  residential proxies, including health checks and locality awareness.
- **Alpha camoufox track.** v0.1 pins `camoufox[geoip] >=0.4.0,<0.5.0`.
  The 0.5.x alpha line tracks Firefox 130+; once it stabilises ghostpress
  will offer it as an opt-in extras target.
- **Resumable captures.** Today a captcha wall ends the run with whatever
  was captured. A future mode would persist mid-flight state and let the
  operator resume after solving the challenge by hand.
