# Prompt mode

`ghostpress build --prompt "<natural language>"` lets you describe the
target instead of typing the URL. ghostpress asks Claude Opus 4.7 for
1–3 candidate URLs, you pick one, and the standard `build` flow runs
against it. The intent is not to replace `ghostpress build <url>` —
it's the same engine — but to remove the "what's the right URL on this
site" friction when you don't already know it. The Anthropic SDK call
lives in `ghostpress.prompt.suggest`.

## Setup

Two requirements:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic   # already a ghostpress dependency, but pin it explicitly if you isolated the install
```

The SDK is imported lazily inside `suggest()` so the rest of ghostpress
doesn't pay the import cost when you're not using prompt mode.

## How it works

The flow is four steps:

1. You run `ghostpress build --prompt "<your prompt>"`.
2. ghostpress calls `ghostpress.prompt.suggest(prompt)`, which sends the
   prompt to Claude Opus 4.7 (`claude-opus-4-7`) via the Anthropic SDK.
3. Claude returns 1–3 `PromptCandidate` objects, each with a `url`, a
   `why` (one-sentence reasoning), and `expected_endpoints` (the
   endpoints Claude expects ghostpress to surface from that URL).
4. You pick a candidate. The standard `ghostpress build <url>` flow
   takes over from there — sniff via camoufox, manifest, codegen.

Step 4 is the same code path as if you had typed the URL directly. The
output is identical; the only difference is the URL discovery step.

## What Claude sees

The system prompt is short on purpose, so a Reddit reader reading this
doc knows exactly what's being shipped to Anthropic:

```
You suggest the best public URL to sniff for the user's goal. Return
ONLY a JSON object: {"candidates": [{"url": "https://...", "why": "...",
"expected_endpoints": ["..."]}]}. 1-3 candidates. No prose, just JSON.
```

That's the full system prompt — defined as `_SYSTEM_PROMPT` in
`src/ghostpress/prompt.py`. The user message is your prompt verbatim.

The system block is sent with `cache_control={"type": "ephemeral"}`, so
the prompt-cache hits when you iterate on the same target. The first
call pays the system-prompt tokens; subsequent calls within the cache
window read from cache.

## Caching

We cache the *response*, not just the prompt prefix. The cache shape:

- Directory: `~/.cache/ghostpress/prompt/` (the literal value of
  `ghostpress.prompt.PROMPT_CACHE_DIR`, expanded via `os.path.expanduser`).
- Key: first 32 hex chars of `sha256(prompt)`.
- File: `<key>.json` containing the `PromptSuggestion` JSON.
- TTL: 24 hours, checked against the file's mtime.

Identical prompts within 24 hours skip the network call entirely. If
you want a fresh suggestion, change the prompt or delete the cache
file. Failed cache reads (corrupted JSON, OS errors) fall through to
the live call silently.

## Failure modes

Three errors users hit, with the actual error string each one returns
and the recovery:

### `ANTHROPIC_API_KEY not set`

```
RuntimeError: ANTHROPIC_API_KEY not set — see docs/prompt_mode.md
```

`suggest()` raises this before doing anything else. Recovery: export
the key in your shell, or set it inline:

```bash
ANTHROPIC_API_KEY=sk-ant-... ghostpress build --prompt "..."
```

### Invalid JSON response

If Claude returns non-JSON text, `json.loads(text)` raises
`json.JSONDecodeError`. This is rare with Opus 4.7 on this prompt
shape, but possible. Recovery: re-run; the cache won't have stored a
bad response (we only write to cache after a successful parse).

### No candidates returned

If Claude returns valid JSON with an empty `candidates` array, the
`PromptSuggestion` validates but contains nothing to pick from.
Recovery: rephrase the prompt with more specifics — domain, action,
expected resource — and re-run.

## Using a different model

`suggest()` takes a `model=` keyword argument:

```python
from ghostpress.prompt import suggest

suggestion = await suggest(
    "amazon laptop reviews under $500",
    model="claude-haiku-4-5-20251001",  # cheaper / faster
)
```

The default is `claude-opus-4-7`, the latest Opus alias as of build
time. Other valid choices:

- `claude-sonnet-4-6` — middle of the road on cost and quality.
- `claude-haiku-4-5-20251001` — cheapest, fastest. URL suggestions for
  well-known sites are reliable on Haiku; long-tail targets are
  hit-or-miss.

The CLI wrapping in `ghostpress build --prompt` uses the default; if
you want to override, call `suggest()` directly from a Python script
and pass the URL into `ghostpress.build.build`.

## Privacy note

What gets sent to Anthropic when you use prompt mode:

- **Your prompt**, verbatim, as the user message.
- **The system prompt** (the 50-token block above).

What does *not* get sent:

- Any HAR data.
- Any captured headers, cookies, or request bodies.
- Any response content from the eventual sniff.
- The contents of `~/.cache/ghostpress/prompt/` are local to your
  machine; we don't upload them.

The prompt-suggestion call happens *before* sniffing. Once you pick a
candidate URL, sniff runs locally against the target — that traffic
never touches Anthropic. The split is deliberate: only the
URL-discovery step is LLM-mediated, so we don't have to send scraped
data to a third party. If you don't want to send your prompt to
Anthropic at all, don't use prompt mode — `ghostpress build <url>` is
unchanged and runs entirely locally.

## See also

- [positioning.md](positioning.md) — where prompt mode fits in the
  ghostpress vs printing-press picture.
- [codegen_format.md](codegen_format.md) — what the build pipeline
  produces once a URL is chosen.
- [../README.md](../README.md) — the top-level pitch.
