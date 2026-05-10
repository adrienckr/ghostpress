# ghostpress as a Claude Code MCP server

Registering ghostpress as an MCP server lets Claude Code drive a real stealth browser inside its tool surface. The agent can open a session, navigate to a bot-protected page, read the rendered DOM as markdown, capture network traffic, and export a printing-press manifest — all in one conversation, without ever leaving the editor.

## Prerequisites

- ghostpress installed (`pip install ghostpress`).
- camoufox binaries already fetched: `python -m camoufox fetch`.
- Claude Code with the `mcp` subcommand available.

## Register the server

```bash
claude mcp add ghostpress -- ghostpress mcp
```

The trailing `ghostpress mcp` is the exact subcommand declared in `cli.py` — it boots the MCP server on stdio. For users who prefer hand-editing config, the equivalent block in `~/.claude/mcp.json` is:

```json
{
  "mcpServers": {
    "ghostpress": {
      "command": "ghostpress",
      "args": ["mcp"]
    }
  }
}
```

## Confirm the tools are loaded

```bash
claude mcp list
```

You should see nine tools, all prefixed `stealth_`:

```
stealth_session_open
stealth_session_close
stealth_navigate
stealth_click
stealth_fill
stealth_read_page
stealth_screenshot
stealth_capture_har
stealth_export_manifest
```

## First task

Drop this prompt into a Claude Code conversation:

> Use the ghostpress MCP server to fetch and summarize https://news.ycombinator.com.
> Open a stealth session, navigate to the URL, read the page as markdown, then close
> the session. Return the top three story titles.

Claude will chain `stealth_session_open` → `stealth_navigate` → `stealth_read_page` → `stealth_session_close` and answer from the markdown digest. No browser window, no manual scraping.

## Multi-step capture inside Claude

For a printing-press handoff in one shot:

> Open a stealth session against https://httpbin.org/get, capture HAR for 10 seconds
> with stealth_capture_har, then call stealth_export_manifest with name="httpbin" and
> source_url="https://httpbin.org/get". Save the manifest JSON to ./httpbin.json.

The agent will pipe the HAR returned from `stealth_capture_har` straight into `stealth_export_manifest`, which emits a printing-press v4-compatible manifest (`schema_version: 1`).
