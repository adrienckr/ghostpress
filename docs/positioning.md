# Positioning: ghostpress vs printing-press

This doc exists because the question comes up the moment anyone reads both
project READMEs: aren't these the same tool? They are not. They share a
paradigm, diverge on the wedge, and stay friendly at the seams.

## TL;DR

[printing-press](https://printingpress.dev) generates agent-optimized CLIs
from HAR files, OpenAPI specs, and live sites; its core thesis is
token-efficient compound CLIs backed by local SQLite mirrors, with Go as
the primary output. ghostpress generates Python CLIs, MCP servers, and
Claude Code skills from the API surface of *bot-protected* sites — captured
through a stealth Firefox build (camoufox) — in one command. We share the
"sniffed-API → CLI" paradigm. We diverge on capture surface, codegen
language, and product thesis. The two are deliberately complementary: a
ghostpress manifest is printing-press v4 compatible, so you can pipe one
into the other if you want each project's strengths on the same target.

## What both tools share

- **The paradigm.** Capture a site's actual HTTP traffic, normalize it into
  a manifest, then generate a callable surface from the manifest. We did
  not invent this; printing-press defined it.
- **MCP-friendly output.** Both projects emit MCP servers as a first-class
  artifact, not an afterthought, because that's the shape agents consume.
- **Manifest schema.** ghostpress emits `schema_version=1` manifests in
  the printing-press v4 shape (`endpoints[]` with `method`, `url_template`,
  `response_content_type`, `request_count`, `sample`). The fixture in
  `tests/fixtures/manifest_v1.json` is pinned in CI to keep that contract
  honest.
- **MIT licensed.** Both projects ship under MIT and intend to stay that
  way.

## Where we diverge

|                            | printing-press                | ghostpress                                       |
|----------------------------|-------------------------------|--------------------------------------------------|
| Capture surface            | Plain HTTP / HAR import       | Stealth Firefox (camoufox)                       |
| Bot-protected sites        | Manual HAR export only        | Native, one command                              |
| One-shot URL → CLI         | No (HAR step manual)          | Yes (`ghostpress build <url>`)                   |
| Prompt → CLI               | No                            | Yes (`ghostpress build --prompt`)                |
| Output formats             | Go CLI + MCP + OpenClaw       | Python CLI + MCP + Claude Skill + per-CLI README |
| Compound queries           | Yes                           | No (out of scope)                                |
| Local SQLite mirror        | Yes                           | No (out of scope)                                |
| Token-efficient design     | Core thesis                   | Not specifically optimized                       |

A few of these rows deserve more than a cell.

### Capture surface

printing-press accepts a HAR file you produce yourself — typically by
opening Chrome DevTools, hitting record, and exporting. That's a clean
input format and it's intentional: the project's wedge is what happens
*after* capture, not the capture step. For a site that gates on bot
detection (Cloudflare interactive challenges, Akamai Bot Manager,
PerimeterX, hCaptcha-on-load) the HAR-export-from-real-browser flow still
works, but it's manual and per-target.

ghostpress's wedge is exactly that step. `ghostpress sniff <url>` launches
camoufox (a patched Firefox that defeats passive fingerprinting at the
C++ level) and produces the HAR for you, in 30 seconds, on a target that
would otherwise reject vanilla Playwright on the first request. See
[../docs/architecture.md](architecture.md) for the camoufox details.

### One-shot URL → CLI

`ghostpress build <url>` collapses sniff + manifest + codegen into a
single command. The internals live in `ghostpress.build.build` — sniff
runs first, the manifest is loaded back from disk, `spec_from_manifest`
turns it into a `CodegenSpec`, and `generate_all` fans out across the
requested formats. End-to-end on a cooperative target it finishes in well
under a minute.

### Output formats

printing-press emits Go binaries — its default codegen target — plus MCP
and OpenClaw integrations. ghostpress emits Python: a Typer CLI
(`cli.py`), an MCP stdio server (`mcp.py`), a Claude Code skill
(`skill.md`), and a per-CLI `README.md`. The split mirrors the audiences:
printing-press is for users who want a single Go binary they can drop on
a server; ghostpress is for users who already live inside a Python /
Claude Code workflow and want the artifact to feel native there. See
[codegen_format.md](codegen_format.md) for the artifact details.

### Compound queries and local SQLite mirror

These are first-class in printing-press and deliberately absent from
ghostpress. printing-press's thesis — that compound, token-efficient
queries against a local mirror beat repeated remote round-trips — is the
right thesis for an agent that's going to live with a target API for
weeks. We don't try to compete on it. ghostpress treats every command as
a single HTTP call against the remote service; if you need the
local-mirror story, that's printing-press's win.

### Token efficiency

printing-press shapes its output for minimal token cost — that's a
stated, measured goal. ghostpress's generated CLIs are not specifically
optimized for that. We expose `--raw` and rely on `rich.print_json` for
formatted output, which is fine for ad-hoc human use and for agents that
have headroom, but it's not a tuned token surface. If your workload is
agent-driven and token-bound, this matters; pick printing-press.

## When to pick which

Pick **printing-press** when:

- You want compound queries across multiple endpoints in one CLI call.
- You want a local SQLite mirror so the agent can query without round-trips.
- Token efficiency is the primary constraint.
- You're happy producing the HAR yourself, or your target is plain HTTP
  with no bot wall.
- You want a Go binary as the deliverable.

Pick **ghostpress** when:

- The target gates on bot detection and you want the capture step
  automated.
- You want one command from URL (or natural-language prompt) to a
  callable artifact.
- You want Python output that drops into a Typer/MCP/Claude Code workflow.
- You want a Claude Code skill emitted alongside the CLI for free.
- You're operating ad-hoc — quick captures, one-off agents, throwaway
  scripts — and the SQLite-mirror story is overkill.

These lists are not exclusive. There are workloads where both apply; see
the next section.

## Why we don't compete on token efficiency

printing-press owns the token-efficient-CLI thesis cleanly. The project
lays it out, measures it, and shapes its codegen around it. We respect
that and don't try to beat them there. ghostpress's generated commands
print readable JSON by default and offer `--raw` for pipelines; the
template at `src/ghostpress/templates/cli.py.jinja` is intentionally
boring so users who want a different shape can fork it. If you need a
token-optimized CLI, run printing-press over the manifest ghostpress
captured.

## Are they complementary?

Yes. ghostpress's output `manifest.json` is byte-compatible with
printing-press v4 — same `schema_version`, same field shapes. The flow
that gets you both wins:

```bash
# Capture the bot-protected target with ghostpress.
ghostpress sniff https://example.com --out ./capture --duration 30

# Hand the HAR to printing-press for its codegen.
printing-press --har ./capture/har.json --name example
```

You get ghostpress's stealth capture and printing-press's
token-efficient, SQLite-backed Go CLI. The seam is the manifest and we
keep it stable on purpose.

## Acknowledgments

printing-press is the prior art that defined this paradigm. Matt Van
Horn shipped the "sniff a site, generate an agent-shaped CLI" idea
publicly first, with the stronger thesis (compound queries, local
mirroring, token efficiency) and the more polished story. ghostpress
exists because we hit a target printing-press's HAR-import step couldn't
reach — a site that rejected every Chromium automation we threw at it —
and we wanted a one-command flow that started with the URL. We built on
the shoulders of printing-press's work, with a different wedge. The
manifest compatibility is deliberate; the friendliness is deliberate;
the absence of overlap on compound-queries / SQLite / token-tuning is
deliberate. If you're choosing between them, choose by wedge, not by
loyalty.
