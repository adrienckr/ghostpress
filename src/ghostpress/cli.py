"""``ghostpress`` Typer CLI.

Five commands:

* ``ghostpress build <url>`` — URL -> CLI in 60 seconds. Sniffs the target
  and generates a Typer CLI, MCP server, Claude skill, and README in one shot.
* ``ghostpress sniff <url>`` — one-shot stealth capture, writes har.json +
  manifest.json into ``--out``.
* ``ghostpress mcp`` — start the MCP server on stdio.
* ``ghostpress run <flow.yaml>`` — execute a multi-step flow.
* ``ghostpress gallery`` — list bundled example CLIs.
"""

from __future__ import annotations

import typer

app = typer.Typer(
    name="ghostpress",
    help="URL → CLI in 60 seconds. Stealth-browser sniff + codegen.",
    add_completion=False,
    no_args_is_help=True,
)

__all__ = [
    "app",
    "build_command",
    "gallery_command",
    "mcp_command",
    "run_command",
    "sniff_command",
]


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


@app.command("build")
def build_command(
    url_or_prompt: str | None = typer.Argument(None, help="URL to build a CLI for, or omit and use --prompt"),
    prompt: str | None = typer.Option(None, "--prompt", "-p", help="Natural-language description; ghostpress picks the URL."),
    out: str = typer.Option("./out", "--out", "-o", help="Output base directory."),
    duration: float = typer.Option(30.0, "--duration", "-d", help="Sniff window seconds."),
    name: str | None = typer.Option(None, "--name", "-n", help="CLI name (defaults to URL host slug)."),
    headed: bool = typer.Option(False, "--headed", help="Visible browser."),
    proxy: str | None = typer.Option(None, "--proxy"),
    keep_secrets: bool = typer.Option(False, "--keep-secrets", help="Replay auth headers in the generated CLI."),
    formats: str = typer.Option("python_cli,mcp_server,claude_skill,readme", "--formats", help="Comma-separated codegen formats."),
) -> None:
    """URL → CLI in 60 seconds. The headline command."""

    import asyncio

    from rich.console import Console

    from ghostpress._types import BrowserProfile, BuildOptions, ProxyConfig
    from ghostpress.build import build

    console = Console(stderr=True)

    target_url = url_or_prompt
    if prompt:
        from ghostpress.prompt import suggest

        suggestion = asyncio.run(suggest(prompt))
        if not suggestion.candidates:
            console.print("[red]no candidate URLs returned[/red]")
            raise typer.Exit(1)
        console.print("[bold]Candidate URLs:[/bold]")
        for i, c in enumerate(suggestion.candidates, 1):
            console.print(f"  [{i}] {c.url} — {c.why}")
        target_url = suggestion.candidates[0].url
        console.print(f"[dim]using #1: {target_url}[/dim]")

    if not target_url:
        console.print("[red]must provide URL or --prompt[/red]")
        raise typer.Exit(1)

    profile = BrowserProfile(headless=not headed, geoip=True)
    proxy_cfg = ProxyConfig(server=proxy) if proxy else None
    options = BuildOptions(
        url=target_url,
        out_dir=out,
        name=name,
        duration_seconds=duration,
        profile=profile,
        proxy=proxy_cfg,
        keep_secrets=keep_secrets,
        formats=[f.strip() for f in formats.split(",") if f.strip()],
    )

    try:
        result = asyncio.run(build(options))
    except RuntimeError as exc:
        console.print(f"[red]build failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    console.print(
        f"[green]built[/green] {result.command_count} commands in "
        f"{result.elapsed_seconds:.1f}s"
    )
    console.print(f"  out: {result.out_dir}")
    for a in result.artifacts:
        console.print(f"  [dim]→[/dim] {a}")
    if result.captcha_detected:
        console.print(f"  [yellow]captcha:[/yellow] {result.captcha_signal}")


@app.command("gallery")
def gallery_command() -> None:
    """List bundled example CLIs."""

    from pathlib import Path

    from rich.console import Console
    from rich.table import Table

    console = Console()
    here = Path(__file__).parent.parent.parent / "examples" / "gallery"
    if not here.exists():
        console.print("[yellow]no gallery yet[/yellow]")
        return

    table = Table(title="ghostpress gallery")
    table.add_column("name")
    table.add_column("source")
    table.add_column("commands")
    for entry in sorted(here.iterdir()):
        if not entry.is_dir():
            continue
        n_cmds = "?"
        source = "(see README)"
        table.add_row(entry.name, source, n_cmds)
    console.print(table)
