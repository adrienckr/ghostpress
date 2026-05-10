# Standalone HAR capture

If all you need is a HAR file — no printing-press, no Claude Code, no MCP — ghostpress works as a one-shot stealth recorder. The output is a standard HTTP Archive 1.2 file you can feed into any tool that accepts HAR input.

## Capture

```bash
ghostpress sniff https://example.com --out ./capture
```

Defaults to a 30-second headless window. The HAR lands at `./capture/har.json` alongside a `manifest.json` (which you can ignore if you only want the raw archive).

## Inspect

The HAR is plain JSON. Open it in:

- **Firefox devtools**: Network tab → right-click → Import HAR. The full request/response timeline materializes as if you had recorded it live.
- **Chrome devtools**: Network tab → drag-and-drop the file onto the panel.
- **`har-viewer`** or any other HAR-aware viewer.

For a quick smoke test on the command line:

```bash
jq '.log.entries | length' ./capture/har.json
jq '.log.entries[0].request.url' ./capture/har.json
```

## Headed mode for interactive captures

Some flows only fire the requests you care about after a human clicks through them — a sign-in form, a cookie banner, a multi-step checkout. Use `--headed --interact`:

```bash
ghostpress sniff https://example.com \
  --out ./capture \
  --headed \
  --interact \
  --duration 180
```

The browser window opens and stays up for the full duration. Drive it manually; ghostpress records every request the page makes during that window.

## Filter by content type

Once you have the HAR, common follow-ups with `jq`:

```bash
# All JSON API responses
jq '[.log.entries[] | select(.response.content.mimeType | startswith("application/json"))]' \
  ./capture/har.json > api-only.json

# Distinct endpoints (method + URL)
jq -r '.log.entries[] | "\(.request.method) \(.request.url)"' \
  ./capture/har.json | sort -u

# Just the POST bodies
jq '.log.entries[] | select(.request.method == "POST") | .request.postData' \
  ./capture/har.json
```
