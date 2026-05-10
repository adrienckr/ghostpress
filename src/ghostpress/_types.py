"""Shared Pydantic models and type aliases.

Module is private (`_types`) because callers should import from
``ghostpress`` directly. Anything re-exported in :mod:`ghostpress` is public.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JsonDict = dict[str, Any]


# ---------------------------------------------------------------------------
# HAR (HTTP Archive 1.2 — http://www.softwareishard.com/blog/har-12-spec/)
# ---------------------------------------------------------------------------


class _HARBase(BaseModel):
    model_config = ConfigDict(extra="allow")


class HARRequest(_HARBase):
    method: str
    url: str
    httpVersion: str = "HTTP/1.1"
    headers: list[JsonDict] = Field(default_factory=list)
    queryString: list[JsonDict] = Field(default_factory=list)
    cookies: list[JsonDict] = Field(default_factory=list)
    postData: JsonDict | None = None
    headersSize: int = -1
    bodySize: int = -1


class HARResponse(_HARBase):
    status: int
    statusText: str = ""
    httpVersion: str = "HTTP/1.1"
    headers: list[JsonDict] = Field(default_factory=list)
    cookies: list[JsonDict] = Field(default_factory=list)
    content: JsonDict = Field(default_factory=dict)
    redirectURL: str = ""
    headersSize: int = -1
    bodySize: int = -1


class HAREntry(_HARBase):
    startedDateTime: str
    time: float
    request: HARRequest
    response: HARResponse
    cache: JsonDict = Field(default_factory=dict)
    timings: JsonDict = Field(default_factory=dict)
    serverIPAddress: str | None = None
    pageref: str | None = None


class HARLog(_HARBase):
    version: str = "1.2"
    creator: JsonDict = Field(
        default_factory=lambda: {"name": "ghostpress", "version": "0.1.0"}
    )
    browser: JsonDict | None = None
    pages: list[JsonDict] = Field(default_factory=list)
    entries: list[HAREntry] = Field(default_factory=list)


class HAR(_HARBase):
    log: HARLog


# ---------------------------------------------------------------------------
# Endpoint manifest (printing-press v4 compatible — schema_version=1)
# ---------------------------------------------------------------------------


class EndpointSample(BaseModel):
    """A representative request/response pair captured for an endpoint."""

    status: int
    request_headers: dict[str, str] = Field(default_factory=dict)
    request_body_preview: str | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body_preview: str | None = None
    response_size_bytes: int = 0


class Endpoint(BaseModel):
    method: str
    url_template: str
    response_content_type: str | None = None
    request_count: int = 1
    sample: EndpointSample | None = None


class Manifest(BaseModel):
    """printing-press-compatible endpoint manifest.

    The ``schema_version`` and field shapes follow printing-press v4. We keep a
    pinned fixture in ``tests/fixtures/manifest_v1.json`` so any drift surfaces
    in CI.
    """

    schema_version: int = 1
    name: str
    source_url: str
    capture_time: str  # ISO 8601 UTC
    user_agent: str | None = None
    endpoints: list[Endpoint] = Field(default_factory=list)
    notes: str | None = None


# ---------------------------------------------------------------------------
# Browser configuration
# ---------------------------------------------------------------------------


class BrowserProfile(BaseModel):
    """Per-session camoufox profile.

    Most fields are passed straight through to the camoufox launcher. Camoufox
    auto-generates fingerprint internals via BrowserForge; this struct only
    captures the high-level operator choices.
    """

    headless: bool = True
    locale: str | None = None
    timezone: str | None = None
    geoip: bool = True
    viewport: tuple[int, int] | None = None
    user_data_dir: str | None = None
    extra_launch_args: dict[str, Any] = Field(default_factory=dict)


class ProxyConfig(BaseModel):
    """Proxy spec in Playwright/camoufox-compatible shape."""

    server: str  # e.g. "http://user:pass@host:port" or "socks5://host:port"
    bypass: list[str] = Field(default_factory=list)
    username: str | None = None
    password: str | None = None


# ---------------------------------------------------------------------------
# Sniff options
# ---------------------------------------------------------------------------


class SniffOptions(BaseModel):
    url: str
    out_dir: str
    duration_seconds: float = 30.0
    name: str | None = None  # for the manifest; defaults to host of url
    profile: BrowserProfile = Field(default_factory=BrowserProfile)
    proxy: ProxyConfig | None = None
    interact: bool = False  # if True, leave the window open for the operator
    notes: str | None = None


class SniffResult(BaseModel):
    har_path: str
    manifest_path: str
    endpoint_count: int
    captcha_detected: bool = False
    captcha_signal: str | None = None
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# MCP tool result types
# ---------------------------------------------------------------------------


class ToolResult(BaseModel):
    """Generic envelope for MCP tool responses."""

    ok: bool = True
    error: str | None = None


class NavigateResult(ToolResult):
    final_url: str = ""
    status: int = 0
    title: str = ""


class ClickResult(ToolResult):
    selector: str = ""


class FillResult(ToolResult):
    selector: str = ""


class ReadPageResult(ToolResult):
    title: str = ""
    url: str = ""
    markdown: str = ""


class ScreenshotResult(ToolResult):
    png_base64: str = ""
    width: int = 0
    height: int = 0


class CaptureHarResult(ToolResult):
    har: HAR | None = None
    duration_seconds: float = 0.0
    captcha_detected: bool = False


class ExportManifestResult(ToolResult):
    manifest: Manifest | None = None


class SessionOpenResult(ToolResult):
    session_id: str = ""


class SessionCloseResult(ToolResult):
    session_id: str = ""


# ---------------------------------------------------------------------------
# Flow (for `ghostpress run flow.yaml`)
# ---------------------------------------------------------------------------


FlowAction = Literal[
    "navigate",
    "click",
    "fill",
    "wait",
    "read_page",
    "screenshot",
    "capture_har",
    "export_manifest",
]


class FlowStep(BaseModel):
    action: FlowAction
    args: dict[str, Any] = Field(default_factory=dict)
    name: str | None = None


class Flow(BaseModel):
    name: str
    description: str | None = None
    profile: BrowserProfile = Field(default_factory=BrowserProfile)
    proxy: ProxyConfig | None = None
    steps: list[FlowStep]


# ---------------------------------------------------------------------------
# Codegen
# ---------------------------------------------------------------------------


class GeneratedCommand(BaseModel):
    """A single Typer/MCP command generated from one Endpoint."""

    name: str  # e.g. "users-get"
    method: str
    url_template: str
    path_params: list[str] = Field(default_factory=list)  # ordered Typer args
    query_params: dict[str, str] = Field(default_factory=dict)  # name -> default
    body_fields: dict[str, str] = Field(default_factory=dict)  # name -> default
    body_is_raw: bool = False
    headers: dict[str, str] = Field(default_factory=dict)  # replayed (no secrets)
    description: str = ""


class CodegenSpec(BaseModel):
    """Inputs to every codegen module — derived once from a Manifest, reused."""

    name: str  # CLI name, e.g. "amazon-reviews"
    package_slug: str  # import-safe slug, e.g. "amazon_reviews"
    source_url: str
    base_url: str  # scheme://host (no path)
    user_agent: str | None = None
    keep_secrets: bool = False
    commands: list[GeneratedCommand]
    schema_version: int = 1


class GeneratedArtifact(BaseModel):
    """One file emitted by a codegen module."""

    path: str  # relative to the build out_dir
    content: str
    executable: bool = False


class BuildOptions(BaseModel):
    url: str
    out_dir: str
    name: str | None = None  # CLI name; defaults to derived slug
    duration_seconds: float = 30.0
    profile: BrowserProfile = Field(default_factory=BrowserProfile)
    proxy: ProxyConfig | None = None
    keep_secrets: bool = False
    formats: list[str] = Field(
        default_factory=lambda: ["python_cli", "mcp_server", "claude_skill", "readme"]
    )
    interact: bool = False


class BuildResult(BaseModel):
    out_dir: str
    har_path: str
    manifest_path: str
    artifacts: list[str] = Field(default_factory=list)  # relative paths written
    command_count: int = 0
    captcha_detected: bool = False
    captcha_signal: str | None = None
    elapsed_seconds: float = 0.0


class PromptCandidate(BaseModel):
    url: str
    why: str
    expected_endpoints: list[str] = Field(default_factory=list)


class PromptSuggestion(BaseModel):
    prompt: str
    candidates: list[PromptCandidate]


__all__ = [
    "HAR",
    "BrowserProfile",
    "BuildOptions",
    "BuildResult",
    "CaptureHarResult",
    "ClickResult",
    "CodegenSpec",
    "Endpoint",
    "EndpointSample",
    "ExportManifestResult",
    "FillResult",
    "Flow",
    "FlowAction",
    "FlowStep",
    "GeneratedArtifact",
    "GeneratedCommand",
    "HAREntry",
    "HARLog",
    "HARRequest",
    "HARResponse",
    "JsonDict",
    "Manifest",
    "NavigateResult",
    "PromptCandidate",
    "PromptSuggestion",
    "ProxyConfig",
    "ReadPageResult",
    "ScreenshotResult",
    "SessionCloseResult",
    "SessionOpenResult",
    "SniffOptions",
    "SniffResult",
    "ToolResult",
]
