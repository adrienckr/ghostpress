"""Tests for ``ghostpress.prompt`` (Anthropic-backed URL suggester with cache)."""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

import pytest

from ghostpress._types import PromptCandidate, PromptSuggestion
from ghostpress.prompt import suggest


def _cache_path(prompt_text: str, base: Path) -> Path:
    key = hashlib.sha256(prompt_text.encode()).hexdigest()[:32]
    return base / f"{key}.json"


async def test_missing_api_key_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("ghostpress.prompt.PROMPT_CACHE_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        await suggest("anything")


async def test_cache_hit_returns_cached_value(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("ghostpress.prompt.PROMPT_CACHE_DIR", str(tmp_path))

    cached = PromptSuggestion(
        prompt="amazon reviews",
        candidates=[
            PromptCandidate(
                url="https://amazon.com/x",
                why="cached",
                expected_endpoints=["/api/reviews"],
            )
        ],
    )
    target = _cache_path("amazon reviews", tmp_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(cached.model_dump_json())

    def _fail_import(*_args, **_kwargs):
        raise AssertionError("anthropic should not be imported on cache hit")

    fake_module = types.ModuleType("anthropic")
    fake_module.AsyncAnthropic = _fail_import  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    result = await suggest("amazon reviews")
    assert result.candidates[0].why == "cached"


async def test_cache_miss_calls_anthropic_and_writes_cache(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("ghostpress.prompt.PROMPT_CACHE_DIR", str(tmp_path))

    class _FakeBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class _FakeResponse:
        def __init__(self, text: str) -> None:
            self.content = [_FakeBlock(text)]

    class _FakeMessages:
        async def create(self, **_kwargs):
            return _FakeResponse(
                '{"candidates": [{"url": "https://x", "why": "z", "expected_endpoints": []}]}'
            )

    class _FakeAsyncAnthropic:
        def __init__(self, *_args, **_kwargs) -> None:
            self.messages = _FakeMessages()

    fake_module = types.ModuleType("anthropic")
    fake_module.AsyncAnthropic = _FakeAsyncAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    result = await suggest("brand new prompt")
    assert result.candidates[0].url == "https://x"


async def test_cache_miss_persists_cache_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr("ghostpress.prompt.PROMPT_CACHE_DIR", str(tmp_path))

    class _FakeBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class _FakeResponse:
        def __init__(self, text: str) -> None:
            self.content = [_FakeBlock(text)]

    class _FakeMessages:
        async def create(self, **_kwargs):
            return _FakeResponse(
                '{"candidates": [{"url": "https://y", "why": "w", "expected_endpoints": []}]}'
            )

    class _FakeAsyncAnthropic:
        def __init__(self, *_args, **_kwargs) -> None:
            self.messages = _FakeMessages()

    fake_module = types.ModuleType("anthropic")
    fake_module.AsyncAnthropic = _FakeAsyncAnthropic  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "anthropic", fake_module)

    prompt_text = "another fresh prompt"
    await suggest(prompt_text)
    assert _cache_path(prompt_text, tmp_path).exists()
