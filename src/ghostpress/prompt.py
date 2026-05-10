"""Prompt-to-CLI: turn a natural-language ask into a candidate URL.

Calls Claude Opus 4.7 (``claude-opus-4-7``) via the official ``anthropic``
Python SDK. Cached per-prompt for 24h to keep iteration cheap.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from ghostpress._types import PromptSuggestion

__all__ = ["PROMPT_CACHE_DIR", "suggest"]


PROMPT_CACHE_DIR = "~/.cache/ghostpress/prompt"

_SYSTEM_PROMPT = (
    "You suggest the best public URL to sniff for the user's goal. "
    "Return ONLY a JSON object: "
    '{"candidates": [{"url": "https://...", "why": "...", '
    '"expected_endpoints": ["..."]}]}. '
    "1-3 candidates. No prose, just JSON."
)


async def suggest(
    prompt: str, *, model: str = "claude-opus-4-7"
) -> PromptSuggestion:
    """Ask Claude Opus 4.7 for 1-3 candidate URLs that match the user's prompt."""

    if "ANTHROPIC_API_KEY" not in os.environ:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set — see docs/prompt_mode.md"
        )

    key = hashlib.sha256(prompt.encode()).hexdigest()[:32]
    cache_dir = Path(os.path.expanduser(PROMPT_CACHE_DIR))
    cache_path = cache_dir / f"{key}.json"

    if cache_path.exists():
        try:
            mtime = cache_path.stat().st_mtime
            if time.time() - mtime < 86400:
                return PromptSuggestion.model_validate_json(
                    cache_path.read_text()
                )
        except OSError:
            pass

    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )

    text_blocks = [getattr(b, "text", None) for b in response.content]
    text = next((t for t in text_blocks if t), "")
    data = json.loads(text)
    suggestion = PromptSuggestion.model_validate(
        {"prompt": prompt, "candidates": data["candidates"]}
    )

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(suggestion.model_dump_json())

    return suggestion
