# Manifest format

ghostpress emits a manifest in printing-press v4's expected shape so that
`printing-press --har <ghostpress output> --name X` consumes it directly,
without an adapter step. This document describes every field, the rules
the converter applies, and how the contract is held stable across versions.

## Schema

The top-level type is `ghostpress._types.Manifest`. The full document:

```json
{
  "schema_version": 1,
  "name": "shop.example.com",
  "source_url": "https://shop.example.com/",
  "capture_time": "2026-05-09T12:00:00Z",
  "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
  "endpoints": [
    {
      "method": "GET",
      "url_template": "https://api.shop.example.com/v1/products",
      "response_content_type": "application/json",
      "request_count": 3,
      "sample": {
        "status": 200,
        "request_headers": {
          "accept": "application/json"
        },
        "request_body_preview": null,
        "response_headers": {
          "content-type": "application/json; charset=utf-8"
        },
        "response_body_preview": "{\"items\":[{\"id\":42,\"name\":\"Hex Wrench\"}],\"page\":1,\"total\":2}",
        "response_size_bytes": 118
      }
    },
    {
      "method": "GET",
      "url_template": "https://api.shop.example.com/v1/products/{id}",
      "response_content_type": "application/json",
      "request_count": 2,
      "sample": {
        "status": 200,
        "request_headers": {"accept": "application/json"},
        "request_body_preview": null,
        "response_headers": {"content-type": "application/json; charset=utf-8"},
        "response_body_preview": "{\"id\":42,\"name\":\"Hex Wrench\"}",
        "response_size_bytes": 71
      }
    }
  ],
  "notes": "Golden fixture for printing-press manifest v1; do not edit without bumping schema."
}
```

### Manifest fields

- `schema_version` (int, required) — pinned to `1`. printing-press uses it
  to gate consumption.
- `name` (string, required) — operator-supplied identifier for the target
  surface. Defaults to the host of `source_url` when `--name` is not
  passed. printing-press uses this as the generated client's package name,
  so prefer something stable and human-readable.
- `source_url` (string, required) — the URL passed to `ghostpress sniff`.
  Recorded verbatim; not normalised.
- `capture_time` (string, required) — ISO 8601 UTC timestamp of when the
  manifest was emitted (not when the capture started).
- `user_agent` (string, optional) — `navigator.userAgent` read from the
  page after navigation. Surfaced so downstream consumers can align headers
  if they replay the captured calls.
- `endpoints` (array of `Endpoint`, required) — sorted by
  `(method, url_template)` so the output is byte-stable across runs.
- `notes` (string, optional) — pass-through field driven by
  `--notes` / `SniffOptions.notes`. printing-press preserves it.

### Endpoint fields

Each item in `endpoints` is a `ghostpress._types.Endpoint`:

- `method` (string, required) — uppercased HTTP verb.
- `url_template` (string, required) — see "URL templating rules" below.
- `response_content_type` (string, optional) — the `mimeType` of the first
  response in the group that had one. Useful for printing-press to pick
  serializers.
- `request_count` (int, default `1`) — how many HAR entries collapsed into
  this endpoint after templating.
- `sample` (`EndpointSample`, optional) — a representative request/response
  pair. The converter prefers a 200-OK response when one exists in the
  group; otherwise the first entry.

### EndpointSample fields

- `status` (int, required) — HTTP status code of the sampled response.
- `request_headers` (object, default `{}`) — flattened header map (first
  occurrence wins for duplicates).
- `request_body_preview` (string, optional) — request body text, truncated
  at 4096 bytes.
- `response_headers` (object, default `{}`) — same flattening rules as
  request headers.
- `response_body_preview` (string, optional) — response body text, truncated
  at 4096 bytes.
- `response_size_bytes` (int, default `0`) — declared content size when
  HAR provides it, else the byte-length of the captured body text.

## Stability contract

`schema_version=1` is pinned for the lifetime of the v0.x line.
`tests/fixtures/manifest_v1.json` is the canonical golden manifest; CI
asserts that `ghostpress.manifest.har_to_manifest` against
`tests/fixtures/sample_har.json` produces output equal to that fixture.

If a change to the converter alters the bytes, the fixture test fails, and
either the fixture is updated deliberately (with a changelog entry) or the
converter change is reverted. Treat `manifest_v1.json` as a contract: do
not edit it casually.

## Filtering rules

`har_to_manifest` keeps only entries whose response MIME type starts with
one of:

- `application/json`
- `text/json`
- `application/x-www-form-urlencoded`

Everything else is dropped at conversion time: HTML documents, JS bundles,
CSS, images, fonts, video, WASM. The intent is that the manifest describes
the **API surface**, not the page's static asset graph.

Two further filters apply:

- Entries with `response.status == 0` (in-flight/aborted by the time the
  capture window closed) are dropped.
- The exact MIME match is prefix-based, so charset suffixes like
  `application/json; charset=utf-8` are preserved.

## URL templating rules

`ghostpress.manifest.url_to_template` normalises every URL before grouping:

- **Query strings stripped.** `?expand=1&page=2` is removed; query params
  are not part of the endpoint identity.
- **Fragments stripped.** `#section` is removed.
- **Numeric segments → `{id}`.** A path segment that matches `^\d+$`
  becomes the literal `{id}`. So `/users/42` and `/users/43` collapse into
  `/users/{id}`.
- **UUIDv4 segments → `{uuid}`.** A segment matching the canonical UUID
  pattern becomes `{uuid}`. So
  `/orders/3f1a2c8e-4b5d-4f6a-8e9b-1c2d3e4f5a6b` becomes `/orders/{uuid}`.
- **Host lowercased.** The netloc is normalised to lowercase. Path case
  is preserved.
- **Path params order preserved.** Templating only rewrites segment
  contents; it never reorders or merges segments.

Anything that does not match the numeric or UUID pattern (slugs, hashes,
opaque tokens) is preserved verbatim. If your target uses non-UUID
identifiers in the path, expect those to come through as separate
endpoints; you can post-process the manifest to merge them by hand.

## When to override

The converter is intentionally conservative — it picks defaults that are
right for the common case and surfaces overrides for the rest:

- `--name` (CLI) / `SniffOptions.name` — the manifest's `name` field
  defaults to the target host. Override when one host serves multiple
  unrelated APIs and you want to disambiguate.
- `notes` (`SniffOptions.notes`) — free-form text that ends up in the
  manifest's `notes` field. Use it to record context the schema does not
  capture: the dashboard view that triggered the calls, the auth method,
  the operator who ran the capture.
- `--name` is also useful when the host is generic (a CDN, a multi-tenant
  router) and you want the manifest named after the logical product.

There is currently no flag for changing the MIME allowlist or the
templating rules. If you need that, fork the converter and call
`har_to_manifest` directly from Python.

## Drift handling

If printing-press changes its expected schema in a future version, the
fixture diff catches it: a new printing-press will reject manifest_v1
inputs, and the integration test will fail. The handling plan:

1. Bump `schema_version` to the new integer.
2. Add a converter (or extend `har_to_manifest` with a `schema_version`
   knob) that emits the new shape.
3. Ship a new golden fixture (`manifest_v2.json`) and keep the v1 fixture
   so old printing-press consumers remain testable.
4. Document the migration in the changelog and in this file.

For the v0.x line, `schema_version=1` is the only supported value. Any
manifest carrying a different version is the consumer's responsibility.
