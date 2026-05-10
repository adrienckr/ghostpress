"""Shared pytest fixtures for the ghostpress test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ghostpress._types import HAR

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def sample_har_path() -> Path:
    return FIXTURES_DIR / "sample_har.json"


@pytest.fixture
def sample_har(sample_har_path: Path) -> HAR:
    raw = json.loads(sample_har_path.read_text())
    return HAR.model_validate(raw)


@pytest.fixture
def manifest_v1_path() -> Path:
    return FIXTURES_DIR / "manifest_v1.json"


class FakeLocator:
    """Minimal Playwright-locator-like object whose methods are awaitable."""

    def __init__(self, selector: str, page: FakePage) -> None:
        self.selector = selector
        self._page = page
        self.click = AsyncMock(return_value=None)
        self.fill = AsyncMock(return_value=None)
        self.wait_for = AsyncMock(return_value=None)
        self.count = AsyncMock(return_value=0)


class FakePage:
    """Minimal Playwright Page stand-in for ghostpress unit tests."""

    def __init__(
        self,
        *,
        url: str = "https://example.com/",
        title: str = "Example",
        content_html: str = "<html><body>hi</body></html>",
        inner_text: str = "hi there",
        screenshot_bytes: bytes = b"PNGDATA",
        viewport: dict[str, int] | None = None,
        navigate_status: int = 200,
    ) -> None:
        self.url = url
        self._title = title
        self._content = content_html
        self._inner_text = inner_text
        self._screenshot_bytes = screenshot_bytes
        self.viewport_size: dict[str, int] | None = viewport or {
            "width": 1280,
            "height": 720,
        }
        self._navigate_status = navigate_status
        self.goto_calls: list[tuple[str, dict[str, Any]]] = []
        self.locator_calls: list[str] = []
        self.handlers: dict[str, list[Any]] = {}
        self.removed: list[tuple[str, Any]] = []

    async def goto(self, url: str, **kwargs: Any) -> Any:
        self.goto_calls.append((url, kwargs))
        self.url = url
        response = MagicMock()
        response.status = self._navigate_status
        return response

    def locator(self, selector: str) -> FakeLocator:
        self.locator_calls.append(selector)
        return FakeLocator(selector, self)

    async def title(self) -> str:
        return self._title

    async def content(self) -> str:
        return self._content

    async def inner_text(self, _selector: str) -> str:
        return self._inner_text

    async def screenshot(self, **_kwargs: Any) -> bytes:
        return self._screenshot_bytes

    async def evaluate(self, _expression: str) -> str:
        return "fake-user-agent/1.0"

    def on(self, event: str, handler: Any) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def remove_listener(self, event: str, handler: Any) -> None:
        self.removed.append((event, handler))


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self._page = page
        self.new_page_calls = 0

    async def new_page(self) -> FakePage:
        self.new_page_calls += 1
        return self._page


class FakeCamoufoxCM:
    """Async context manager that mimics ``AsyncCamoufox``."""

    instances: list[FakeCamoufoxCM] = []

    def __init__(self, page: FakePage | None = None, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self._page = page or FakePage()
        self._browser = FakeBrowser(self._page)
        self.entered = False
        self.exited = False
        FakeCamoufoxCM.instances.append(self)

    async def __aenter__(self) -> FakeBrowser:
        self.entered = True
        return self._browser

    async def __aexit__(self, *_exc: Any) -> None:
        self.exited = True


@pytest.fixture
def fake_page() -> FakePage:
    return FakePage()


@pytest.fixture
def fake_camoufox_factory():
    """Returns a callable that produces a FakeCamoufoxCM bound to a given page."""

    FakeCamoufoxCM.instances.clear()

    def _factory(page: FakePage):
        def _ctor(**kwargs: Any) -> FakeCamoufoxCM:
            return FakeCamoufoxCM(page=page, **kwargs)

        return _ctor

    return _factory


@pytest.fixture
def fake_camoufox(fake_page: FakePage, monkeypatch: pytest.MonkeyPatch):
    """Patch AsyncCamoufox in tools and sniff modules. Returns the FakePage."""

    FakeCamoufoxCM.instances.clear()

    def _ctor(**kwargs: Any) -> FakeCamoufoxCM:
        return FakeCamoufoxCM(page=fake_page, **kwargs)

    monkeypatch.setattr("ghostpress.tools.AsyncCamoufox", _ctor)
    monkeypatch.setattr("ghostpress.sniff.AsyncCamoufox", _ctor)
    return fake_page
