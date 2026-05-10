# Codegen format

This is an internal-developer doc for what each codegen module emits. Use
it when you're working on the templates, debugging a generated artifact,
or trying to understand why a particular endpoint became a particular
command. The user-facing entry point is `ghostpress build`; the
orchestration that gets us here lives in `ghostpress.build.build` and
fans out via `ghostpress.codegen.generate_all`.

## The CodegenSpec

Every codegen module consumes a single immutable input: a `CodegenSpec`.
It's produced once by `ghostpress.codegen.spec_from_manifest` from the
captured `Manifest`, then handed to each format's `generate(spec)`
function. The intent is that the spec is the only translation layer —
templates render directly off its fields, no ad-hoc lookups against the
raw manifest.

The relevant types live in `src/ghostpress/_types.py`:

```python
class CodegenSpec(BaseModel):
    name: str                        # CLI name, e.g. "amazon-reviews"
    package_slug: str                # import-safe slug, e.g. "amazon_reviews"
    source_url: str
    base_url: str                    # scheme://host (no path)
    user_agent: str | None = None
    keep_secrets: bool = False
    commands: list[GeneratedCommand]
    schema_version: int = 1
```

- `name` is the kebab-style display name. It's what shows up in the Typer
  app help, the MCP server name, and the skill frontmatter.
- `package_slug` is the underscore-safe variant. It's used for any
  identifier that has to satisfy Python's import rules — the
  `[project.scripts]` entry, the package directory, the MCP tool prefix.
- `base_url` is `scheme://netloc` only; `spec_from_manifest` strips the
  path. Path information lives on each command's `url_template`.
- `keep_secrets` mirrors the `--keep-secrets` build flag. When False
  (the default), `sanitize_headers` drops auth-bearing headers from the
  spec before any template ever sees them.
- `schema_version` is carried through from the manifest for forward
  compatibility; today it's always 1.

Each `GeneratedCommand` describes one endpoint:

```python
class GeneratedCommand(BaseModel):
    name: str                              # e.g. "users-get"
    method: str
    url_template: str
    path_params: list[str]                 # ordered Typer args
    query_params: dict[str, str]           # name -> default
    body_fields: dict[str, str]            # name -> default
    body_is_raw: bool = False
    headers: dict[str, str]                # replayed (no secrets)
    description: str = ""
```

- `name` is unique within the spec; collision handling lives in
  `command_name_from_endpoint` (see "Naming rules" below).
- `path_params` is the ordered list extracted from `{...}` placeholders
  in the URL template. Order matters because Typer turns these into
  positional arguments.
- `query_params` is currently always empty for v1.0 — see "What's
  deliberately omitted".
- `body_fields` vs `body_is_raw` is a one-or-the-other choice made at
  spec-build time: if the sample request body parses as a JSON object,
  one-level keys become `body_fields`; otherwise the whole body is
  treated as raw and `body_is_raw=True`.
- `headers` is whatever survived `sanitize_headers`. If `keep_secrets`
  was True the original auth headers are still there; otherwise they're
  stripped.

## Python CLI output

The Python CLI module (`ghostpress.codegen.python_cli`) emits two
artifacts:

- `cli.py` — a Typer app, executable.
- `pyproject.toml` — pins the runtime deps (`typer`, `httpx`, `rich`)
  and registers a `[project.scripts]` entry so `pip install -e .` makes
  the CLI globally callable.

The `cli.py` template (`src/ghostpress/templates/cli.py.jinja`) maps
each `GeneratedCommand` to one `@app.command(...)`-decorated function:

- Path placeholders (`{id}`, `{uuid}`) become positional Typer
  arguments in the order they appear in the template.
- Query params, when present, become `--name` Typer options with the
  inferred default.
- For non-raw bodies, each `body_fields` key becomes a `--key` option;
  the function builds a `body_payload` dict from non-None options and
  passes it as `json=` to `httpx`.
- For raw bodies, the function takes a single `--body` option that
  accepts either an inline string or `@path/to/file`.
- Sanitized `headers` are baked into the rendered source.
- Two universal flags: `--raw` (skip JSON formatting) and `--timeout`.

Install + run:

```bash
cd out/<name>/
pip install -e .
<name> <command> [args...] [--option value...]
```

The generated CLI has zero dependency on ghostpress itself — it imports
only `typer`, `httpx`, and `rich`. Drop it on any machine with Python
3.10+.

### Argument inference rules

- **Path params** come from `extract_path_params` in
  `ghostpress.codegen._utils`, which finds `{name}` patterns and returns
  them in source order. `-` in a name becomes `_` in the Python
  identifier so it's a valid argument.
- **Query params** are currently empty (see "What's deliberately
  omitted"). The plumbing in the template handles them, so wiring this
  up later is a one-spot change.
- **Body fields** are inferred only when the sample request body parses
  as a JSON object. Top-level keys become field names; their sample
  values become defaults (stringified via `json.dumps` for non-strings).
- **Raw body** — anything that starts with `{` but doesn't parse, or
  anything that doesn't start with `{`, becomes a raw body. The CLI
  takes it via `--body`.

### Auth-header redaction

By default, `sanitize_headers` drops every header whose name matches
(case-insensitive) one of:

- `Authorization`
- `Cookie`
- `Set-Cookie`
- `X-Api-Key`
- `X-Auth-Token`
- `X-Csrf-Token` / `X-Csrf` / `X-Xsrf-Token`
- `X-Amz-Security-Token`
- `Proxy-Authorization`

The full set is `AUTH_HEADER_NAMES` in
`src/ghostpress/codegen/_utils.py`. Add to it there; the change flows
through every generator.

### `--keep-secrets` opt-in

If you actually want the captured auth headers replayed verbatim, pass
`--keep-secrets` at build time. Pass it through:

```bash
ghostpress build https://example.com --out ./out --keep-secrets
```

That sets `BuildOptions.keep_secrets=True` (see `_types.py`), which
flows into `spec_from_manifest`, which short-circuits
`sanitize_headers`. The flag is opt-in for one reason: the artifacts
are designed to be commit-safe by default. If you turn it on, treat the
output directory like the secrets file it now is.

## MCP server output

The MCP module (`ghostpress.codegen.mcp_server`) emits one artifact:

- `mcp.py` — an MCP stdio server, executable.

The template (`src/ghostpress/templates/mcp.py.jinja`) registers one
tool per `GeneratedCommand`. The shape mirrors `cli.py`'s logic: build
the URL by substituting path params, drop None query params, replay
sanitized headers, attach JSON body or raw `content`, run the request
with `httpx.AsyncClient`, return the raw response text wrapped in a
`TextContent`.

Register with Claude Code:

```bash
claude mcp add <name> -- python out/<name>/mcp.py
```

After that, the tools show up in Claude Code with names matching the
generated commands.

### Tool naming convention

MCP tool names cannot contain hyphens; the template substitutes them at
render time:

```jinja
name="{{ cmd.name | replace('-', '_') }}"
```

So the command `users-get` becomes the MCP tool `users_get`. The CLI
keeps the kebab form (Typer is fine with it), the MCP tool gets the
underscore form. Both are derived from the same `GeneratedCommand.name`.

## Claude Code skill output

The skill module (`ghostpress.codegen.claude_skill`) emits one artifact:

- `skill.md` — a Claude Code skill file with frontmatter.

The template (`src/ghostpress/templates/skill.md.jinja`) renders YAML
frontmatter (`name`, `description`) plus a body that documents every
command as a callable action with its method, URL template, and any
parameters. The generated skill cross-references `cli.py` and `mcp.py`
in the same directory.

Install location:

```
~/.claude/skills/<name>/skill.md
```

Frontmatter shape:

```yaml
---
name: <spec.name>
description: Generated CLI for <spec.source_url>. Use when the user asks for actions on this site.
---
```

The description is intentionally generic. Edit it after install if you
want Claude Code to trigger the skill more aggressively or only for
specific phrasings.

## Per-CLI README output

The README module (`ghostpress.codegen.readme`) emits one artifact:

- `README.md` — for the generated artifact directory.

The template (`src/ghostpress/templates/readme.md.jinja`) follows a
fixed four-section convention: install, use (per-command examples),
MCP server registration, Claude Code skill install. It's the file a
user sees when they `cd` into the output directory and want to
remember what they generated three weeks ago.

## Naming rules

Endpoint URL templates collapse to command names through
`command_name_from_endpoint` in `src/ghostpress/codegen/_utils.py`. The
behavior, quoted from its docstring:

- Collapse the URL template to its last meaningful (non-placeholder)
  segment.
- Append `-<method>` if method != GET.
- If the result collides with `taken`, append `-1`, `-2`, ...
- Mutate `taken` so subsequent calls remain collision-free.

Concretely, `GET /api/v2/users/{id}/posts` becomes `posts`. `POST
/api/v2/users` becomes `users-post`. A second `GET /api/v1/users` in
the same manifest collides with the first and becomes `users-1`.

`extract_path_params` is the pair-helper. It finds `{name}` patterns in
the template via regex and returns them in source order, which becomes
the order of Typer's positional arguments.

## Header sanitization

The auth headers in `AUTH_HEADER_NAMES` (above) are dropped by default.
If you want them back, build with `--keep-secrets`. The check is
case-insensitive (`Authorization` and `AUTHORIZATION` both match).

## What's deliberately omitted

v1.0 ships intentionally narrow. The following are not in the codegen
surface:

- **Auth flow inference.** OAuth, signed requests (AWS SigV4, HMAC),
  CSRF token rotation, JWT refresh — none of these are inferred. If the
  captured session was authenticated, the *replay* will work as long as
  the captured headers stay valid; once they expire, you re-capture.
- **Pagination logic.** Cursor-based, page-based, offset-based — none
  are detected. Callers that need to walk a paginated endpoint do it by
  hand.
- **Rate-limit awareness.** No backoff, no `Retry-After` parsing. If
  the server returns 429, the CLI returns 1.
- **Query-param defaults.** The `EndpointSample` shape in the manifest
  doesn't preserve the original recorded request URL — only normalized
  headers and the body preview. Recovering per-endpoint query-param
  defaults from the sample would require threading the raw URL through
  HAR → Manifest, which we did not do for v1.0. There's a
  `TODO(query_params)` comment in `spec_from_manifest` documenting this
  exactly. Today, `query_params={}` for every command; users still pass
  `--name=value` flags at runtime, just without sample-derived defaults.

These are not on the v1.0 backlog because each one needs its own design
discussion (especially auth flow inference — getting that wrong is
worse than not having it at all).

## Customizing the output

The templates live at `src/ghostpress/templates/*.jinja`:

- `cli.py.jinja`
- `mcp.py.jinja`
- `skill.md.jinja`
- `readme.md.jinja`

If you want a different CLI shape — a different framework than Typer, a
different output format than `rich.print_json`, an opinionated
`--output json|table|csv` flag — fork the template. The
`generate(spec)` function in each module is a 30-line wrapper around a
Jinja render; the work is in the template, and the template gets the
full `CodegenSpec` as `spec`. Keep the rendered file's deps minimal so
the generated CLI stays standalone.
