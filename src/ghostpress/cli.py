"""``ghostpress`` Typer CLI.

Three commands:

* ``ghostpress sniff <url>`` — one-shot stealth capture, writes har.json +
  manifest.json into ``--out``.
* ``ghostpress mcp`` — start the MCP server on stdio.
* ``ghostpress run <flow.yaml>`` — execute a multi-step flow.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="ghostpress",
    help="Stealth-browser sniff daemon for printing-press.",
    add_completion=False,
    no_args_is_help=True,
)

__all__ = ["app", "mcp_command", "run_command", "sniff_command"]


@app.command("sniff")
def sniff_command(
    url: str = typer.Argument(..., help="Target URL to capture."),
    out: str = typer.Option("./capture", "--out", "-o", help="Output directory."),
    duration: float = typer.Option(30.0, "--duration", "-d", help="Capture window seconds."),
    name: str | None = typer.Option(None, "--name", "-n", help="Manifest name (defaults to host)."),
    headed: bool = typer.Option(False, "--headed", help="Run with a visible browser window."),
    proxy: str | None = typer.Option(None, "--proxy", help="Proxy URL (scheme://user:pass@host:port)."),
    interact: bool = typer.Option(
        False,
        "--interact",
        help="Keep the window open for interactive operator clicks.",
    ),
) -> None:
    """Capture a HAR + printing-press manifest from a target URL."""

    import asyncio

    from rich.console import Console

    from ghostpress._types import BrowserProfile, ProxyConfig, SniffOptions
    from ghostpress.sniff import sniff

    console = Console(stderr=True)

    profile = BrowserProfile(headless=not headed, geoip=True)
    proxy_cfg = ProxyConfig(server=proxy) if proxy else None
    options = SniffOptions(
        url=url,
        out_dir=out,
        duration_seconds=duration,
        name=name,
        profile=profile,
        proxy=proxy_cfg,
        interact=interact,
    )

    try:
        result = asyncio.run(sniff(options))
    except RuntimeError as exc:
        console.print(f"[red]sniff failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print("[green]sniff complete[/green]")
    console.print(f"  HAR:        {result.har_path}")
    console.print(f"  Manifest:   {result.manifest_path}")
    console.print(f"  Endpoints:  {result.endpoint_count}")
    if result.captcha_detected:
        signal = result.captcha_signal or "unknown"
        console.print(f"  [yellow]Captcha detected:[/yellow] {signal}")
    raise typer.Exit(0)


@app.command("mcp")
def mcp_command() -> None:
    """Start the MCP server on stdio."""

    import asyncio

    from ghostpress.mcp_server import run_stdio

    asyncio.run(run_stdio())


@app.command("run")
def run_command(
    flow_path: str = typer.Argument(..., help="Path to a flow.yaml file."),
    out: str = typer.Option("./runs", "--out", "-o", help="Output directory for evidence."),
) -> None:
    """Execute a multi-step browser flow declared in YAML."""

    import asyncio
    import contextlib
    import uuid
    from pathlib import Path

    import yaml
    from rich.console import Console

    from ghostpress import tools as gp_tools
    from ghostpress._types import HAR, Flow
    from ghostpress.tools import SessionRegistry

    console = Console(stderr=True)

    with open(flow_path) as fh:
        flow_data = yaml.safe_load(fh)
    flow = Flow.model_validate(flow_data)

    run_id = uuid.uuid4().hex[:12]
    run_dir = Path(out) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Flow:[/bold] {flow.name} ([dim]{run_id}[/dim])")
    console.print(f"  output: {run_dir}")

    async def _execute() -> None:
        registry = SessionRegistry()
        session_id: str | None = None
        try:
            open_result = await gp_tools.stealth_session_open(
                registry, profile=flow.profile, proxy=flow.proxy
            )
            if not open_result.ok:
                console.print(f"[red]session_open failed:[/red] {open_result.error}")
                raise typer.Exit(1)
            session_id = open_result.session_id

            for index, step in enumerate(flow.steps):
                step_label = step.name or step.action
                args = dict(step.args or {})
                try:
                    if step.action == "navigate":
                        result = await gp_tools.stealth_navigate(
                            registry,
                            session_id=session_id,
                            url=args["url"],
                            wait_for=args.get("wait_for"),
                            timeout_ms=int(args.get("timeout_ms", 30_000)),
                        )
                    elif step.action == "click":
                        result = await gp_tools.stealth_click(
                            registry,
                            session_id=session_id,
                            selector=args["selector"],
                            timeout_ms=int(args.get("timeout_ms", 10_000)),
                        )
                    elif step.action == "fill":
                        result = await gp_tools.stealth_fill(
                            registry,
                            session_id=session_id,
                            selector=args["selector"],
                            text=args["text"],
                            timeout_ms=int(args.get("timeout_ms", 10_000)),
                        )
                    elif step.action == "wait":
                        seconds = float(args.get("seconds", 1.0))
                        await asyncio.sleep(seconds)
                        result = None
                    elif step.action == "read_page":
                        result = await gp_tools.stealth_read_page(
                            registry, session_id=session_id
                        )
                    elif step.action == "screenshot":
                        result = await gp_tools.stealth_screenshot(
                            registry,
                            session_id=session_id,
                            full_page=bool(args.get("full_page", False)),
                        )
                    elif step.action == "capture_har":
                        result = await gp_tools.stealth_capture_har(
                            registry,
                            session_id=session_id,
                            duration_seconds=float(args.get("duration_seconds", 10.0)),
                        )
                    elif step.action == "export_manifest":
                        if "har_json" in args:
                            har = HAR.model_validate_json(args["har_json"])
                        else:
                            har = HAR.model_validate(args["har"])
                        result = await gp_tools.stealth_export_manifest(
                            har,
                            name=args["name"],
                            source_url=args["source_url"],
                        )
                    else:  # pragma: no cover - guarded by Literal
                        raise ValueError(f"Unknown action: {step.action}")
                except Exception as exc:
                    console.print(
                        f"  [{index:02d}] {step_label}: [red]error[/red] {exc}"
                    )
                    continue

                if result is not None:
                    out_path = run_dir / f"{index:02d}_{step.action}.json"
                    out_path.write_text(result.model_dump_json(indent=2))
                    status = "ok" if getattr(result, "ok", True) else "fail"
                    color = "green" if status == "ok" else "red"
                    console.print(
                        f"  [{index:02d}] {step_label}: [{color}]{status}[/{color}]"
                    )
                else:
                    console.print(
                        f"  [{index:02d}] {step_label}: [green]ok[/green]"
                    )
        finally:
            if session_id is not None:
                with contextlib.suppress(Exception):
                    await gp_tools.stealth_session_close(
                        registry, session_id=session_id
                    )
            with contextlib.suppress(Exception):
                await registry.aclose()

    asyncio.run(_execute())
