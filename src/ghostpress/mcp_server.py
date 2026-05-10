"""MCP server exposing the stealth-browser tool surface over stdio.

Wraps the async tool functions in :mod:`ghostpress.tools`. A single
:class:`SessionRegistry` is shared across the server's lifetime so that
multi-step flows can persist a session across tool calls.
"""

from __future__ import annotations

from typing import Any

try:
    from mcp import types as mcp_types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ImportError as exc:  # pragma: no cover - import-time guard
    raise ImportError(
        "MCP SDK not available. Install ghostpress with the [mcp] extras and re-run."
    ) from exc

try:
    from mcp.server.lowlevel import NotificationOptions
    from mcp.server.models import InitializationOptions
except ImportError:  # pragma: no cover - older SDK shapes
    NotificationOptions = None  # type: ignore[assignment]
    InitializationOptions = None  # type: ignore[assignment]


__all__ = ["build_server", "run_stdio"]


_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "stealth_session_open",
        "description": "Open a stealth camoufox session and return a session_id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "headless": {"type": "boolean", "default": True},
                "locale": {"type": "string"},
                "timezone": {"type": "string"},
                "proxy_server": {"type": "string"},
            },
        },
    },
    {
        "name": "stealth_session_close",
        "description": "Close a previously opened stealth session.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    },
    {
        "name": "stealth_navigate",
        "description": "Navigate the session to a URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "url": {"type": "string"},
                "wait_for": {"type": "string"},
                "timeout_ms": {"type": "integer", "default": 30000},
            },
            "required": ["session_id", "url"],
        },
    },
    {
        "name": "stealth_click",
        "description": "Click the first element matching a CSS selector.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "selector": {"type": "string"},
                "timeout_ms": {"type": "integer", "default": 10000},
            },
            "required": ["session_id", "selector"],
        },
    },
    {
        "name": "stealth_fill",
        "description": "Type text into an input matching a CSS selector.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "selector": {"type": "string"},
                "text": {"type": "string"},
                "timeout_ms": {"type": "integer", "default": 10000},
            },
            "required": ["session_id", "selector", "text"],
        },
    },
    {
        "name": "stealth_read_page",
        "description": "Return the current page as a markdown digest.",
        "inputSchema": {
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
            "required": ["session_id"],
        },
    },
    {
        "name": "stealth_screenshot",
        "description": "Capture a PNG screenshot, base64-encoded.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "full_page": {"type": "boolean", "default": False},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "stealth_capture_har",
        "description": "Capture network events for a duration and return a HAR.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "duration_seconds": {"type": "number"},
            },
            "required": ["session_id", "duration_seconds"],
        },
    },
    {
        "name": "stealth_export_manifest",
        "description": "Convert a HAR JSON string into a printing-press manifest.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "source_url": {"type": "string"},
                "har_json": {"type": "string"},
            },
            "required": ["name", "source_url", "har_json"],
        },
    },
]


def build_server() -> Server:
    """Construct and return an MCP ``Server`` with all stealth tools registered."""

    from ghostpress import tools as gp_tools
    from ghostpress._types import HAR, BrowserProfile, ProxyConfig
    from ghostpress.tools import SessionRegistry

    server = Server("ghostpress")
    registry = SessionRegistry()
    server._ghostpress_registry = registry  # type: ignore[attr-defined]

    @server.list_tools()
    async def _list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name=spec["name"],
                description=spec["description"],
                inputSchema=spec["inputSchema"],
            )
            for spec in _TOOL_DEFS
        ]

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[mcp_types.TextContent]:
        args = arguments or {}

        if name == "stealth_session_open":
            profile_kwargs: dict[str, Any] = {
                "headless": args.get("headless", True),
            }
            if args.get("locale") is not None:
                profile_kwargs["locale"] = args["locale"]
            if args.get("timezone") is not None:
                profile_kwargs["timezone"] = args["timezone"]
            profile = BrowserProfile(**profile_kwargs)
            proxy: ProxyConfig | None = None
            if args.get("proxy_server"):
                proxy = ProxyConfig(server=args["proxy_server"])
            result = await gp_tools.stealth_session_open(
                registry, profile=profile, proxy=proxy
            )
        elif name == "stealth_session_close":
            result = await gp_tools.stealth_session_close(
                registry, session_id=args["session_id"]
            )
        elif name == "stealth_navigate":
            result = await gp_tools.stealth_navigate(
                registry,
                session_id=args["session_id"],
                url=args["url"],
                wait_for=args.get("wait_for"),
                timeout_ms=args.get("timeout_ms", 30_000),
            )
        elif name == "stealth_click":
            result = await gp_tools.stealth_click(
                registry,
                session_id=args["session_id"],
                selector=args["selector"],
                timeout_ms=args.get("timeout_ms", 10_000),
            )
        elif name == "stealth_fill":
            result = await gp_tools.stealth_fill(
                registry,
                session_id=args["session_id"],
                selector=args["selector"],
                text=args["text"],
                timeout_ms=args.get("timeout_ms", 10_000),
            )
        elif name == "stealth_read_page":
            result = await gp_tools.stealth_read_page(
                registry, session_id=args["session_id"]
            )
        elif name == "stealth_screenshot":
            result = await gp_tools.stealth_screenshot(
                registry,
                session_id=args["session_id"],
                full_page=args.get("full_page", False),
            )
        elif name == "stealth_capture_har":
            result = await gp_tools.stealth_capture_har(
                registry,
                session_id=args["session_id"],
                duration_seconds=float(args["duration_seconds"]),
            )
        elif name == "stealth_export_manifest":
            har = HAR.model_validate_json(args["har_json"])
            result = await gp_tools.stealth_export_manifest(
                har, name=args["name"], source_url=args["source_url"]
            )
        else:
            raise ValueError(f"Unknown tool: {name}")

        return [
            mcp_types.TextContent(type="text", text=result.model_dump_json())
        ]

    return server


async def run_stdio() -> None:
    """Run the MCP server on stdio. Entry point for ``ghostpress mcp``."""

    import contextlib

    server = build_server()
    registry = getattr(server, "_ghostpress_registry", None)

    try:
        async with stdio_server() as (read_stream, write_stream):
            if InitializationOptions is not None and NotificationOptions is not None:
                init_options = InitializationOptions(
                    server_name="ghostpress",
                    server_version="0.1.0",
                    capabilities=server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                )
            else:  # pragma: no cover - fallback for SDK shape drift
                init_options = server.create_initialization_options()
            await server.run(read_stream, write_stream, init_options)
    finally:
        if registry is not None:
            with contextlib.suppress(Exception):
                await registry.aclose()
