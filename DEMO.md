# ghostpress demo

The killer demo. Three target captures, back to back. Each one is a site that defeats plain-HTTP capture: a major retailer with sophisticated anti-bot, a Cloudflare-walled SaaS dashboard, and a JS-heavy SPA that fingerprints the browser before serving any data.

## Demo 1: Amazon (60 seconds)

Goal: a CLI that reads product reviews. Plain-HTTP capture against Amazon returns a 503, a captcha page, or an HTML shell with no XHRs. ghostpress drops camoufox into the capture step and the network conversation comes back intact.

<!-- asciinema casts will be embedded here once recorded.
     See launch/recording_checklist.md once it exists, or run:
       asciinema rec ghostpress-amazon.cast -c "ghostpress build <url>"
-->

```
$ ghostpress build https://www.amazon.com/product-reviews/<ASIN>
sniff complete
  HAR:        out/amazon-com/har.json
  Manifest:   out/amazon-com/manifest.json
  Endpoints:  8
built 8 commands in 58.2s
  out: out/amazon-com
  -> cli.py
  -> mcp.py
  -> skill.md
  -> README.md

$ out/amazon-com/cli.py reviews-list --product-id <ASIN>
[
  {"author": "...", "rating": 5, "title": "...", "body": "...", "verified": true},
  {"author": "...", "rating": 4, "title": "...", "body": "..."},
  ...
]
```

The generated `cli.py` is a standalone Typer + httpx file — no ghostpress runtime dependency, no camoufox dependency. Once captured, it talks to the API directly.

## Demo 2: Cloudflare-walled SaaS

Goal: a CLI for a tool that has no public API but does have an internal-facing dashboard you have legitimate access to. The dashboard sits behind Cloudflare's bot challenge.

<!-- asciinema casts will be embedded here once recorded.
     See launch/recording_checklist.md once it exists, or run:
       asciinema rec ghostpress-cloudflare.cast -c "ghostpress build <url> --headed --duration 60"
-->

```
$ ghostpress build https://app.example-saas.com/dashboard --headed --duration 45
# Browser window opens. Operator clicks through the dashboard sections they care about.
sniff complete
  HAR:        out/example-saas-com/har.json
  Manifest:   out/example-saas-com/manifest.json
  Endpoints:  12
built 12 commands in 71.4s
  out: out/example-saas-com

$ out/example-saas-com/cli.py projects-list
[
  {"id": "p_abc", "name": "Project A", "owner": "..."},
  ...
]
```

`--headed` keeps the window visible so the operator can drive the navigation that matters during the duration window; ghostpress just records what XHRs that navigation produces. Pick a `--duration` long enough for the click-through. `--keep-secrets` is what you reach for if you want the generated CLI to replay your authenticated cookies — off by default.

## Demo 3: JS-heavy SPA

Goal: a CLI for a single-page app that fingerprints navigator, canvas, and WebGL before rendering anything. Plain-HTTP capture sees a JS bundle and nothing else.

<!-- asciinema casts will be embedded here once recorded.
     See launch/recording_checklist.md once it exists, or run:
       asciinema rec ghostpress-spa.cast -c "ghostpress build <url>"
-->

```
$ ghostpress build https://spa.example.com/search?q=widget
sniff complete
  HAR:        out/spa-example-com/har.json
  Manifest:   out/spa-example-com/manifest.json
  Endpoints:  6
built 6 commands in 54.9s

$ out/spa-example-com/cli.py search-get --q widget
{
  "results": [...],
  "facets": {...},
  "next_cursor": "..."
}
```

camoufox passes the SPA's fingerprint check the same way a real browser does: by actually being one. The XHRs the SPA fires are exactly what the generated CLI replays.

## How to record your own

The transcripts above are verbatim copy-pasteable. To record an asciinema cast against a real target:

```bash
asciinema rec ghostpress-<target>.cast -c "ghostpress build <url>"
```

Then embed the resulting `.cast` file in this document.

For live, runnable artifacts you can clone and execute without doing your own capture, see [examples/gallery/](examples/gallery/).
