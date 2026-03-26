# BotAudit Sitemap Crawl Mode Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

BotAudit's batch mode (see `SPEC-batch.md`) enables auditing multiple URLs, but requires the user to supply every URL explicitly — either as arguments or via a file. For real-world sites, discovering which pages to audit is itself a significant task.

Most well-maintained websites publish an [XML sitemap](https://www.sitemaps.org/protocol.html) at `/sitemap.xml` or declare one or more sitemap locations in `robots.txt`. This specification introduces a `--crawl` flag that leverages sitemaps to automatically discover auditable URLs, then feeds them into the existing batch pipeline.

Crawl mode does not perform link-following or web crawling in the traditional sense. It is strictly sitemap-based: it fetches and parses sitemap files, extracts `<loc>` entries, and passes the resulting URL list to the batch orchestrator. This keeps behavior predictable, polite to servers, and easy to reason about.

---

## Functional Requirements

### FR-1. Crawl Flag

FR-1.1. The tool SHALL accept a `--crawl` flag that takes a single URL as its value. This URL is the **target origin** — the site whose sitemap(s) will be discovered and parsed.

FR-1.2. The `--crawl` value SHALL be validated using the same rules as positional URL arguments (scheme MUST be `http` or `https`, netloc MUST be present).

FR-1.3. When `--crawl` is specified, the tool SHALL NOT require positional URLs or `--file`. If positional URLs or `--file` are also provided, the tool SHALL combine all sources (crawl-discovered URLs + positional + file), deduplicate per `SPEC-batch.md` FR-3, and run a single batch.

FR-1.4. `--crawl` SHALL NOT be specified more than once. If provided multiple times, the tool SHALL print an error and exit with code 2.

FR-1.5. When `--crawl` is the sole input source and sitemap discovery yields zero URLs, the tool SHALL print an error to stderr and exit with code 2.

### FR-2. Sitemap Discovery

FR-2.1. Given a target origin URL, the tool SHALL attempt to locate sitemaps in the following order:

1. Fetch `robots.txt` at the origin's root (e.g., `https://example.com/robots.txt`) and extract all `Sitemap:` directives.
2. If `robots.txt` is unreachable, unparseable, or contains no `Sitemap:` directives, fall back to the conventional location `{origin}/sitemap.xml`.

FR-2.2. `Sitemap:` directives in `robots.txt` SHALL be parsed case-insensitively (the directive name `Sitemap` is case-insensitive per the robots.txt specification).

FR-2.3. `Sitemap:` directive values SHALL be treated as absolute URLs. Relative URLs SHALL be ignored with a warning to stderr.

FR-2.4. If both `robots.txt` discovery and the `/sitemap.xml` fallback fail (network error, HTTP error, timeout), the tool SHALL print an error to stderr and exit with code 2 when `--crawl` is the sole input source. If positional URLs or `--file` are also present, the tool SHALL print a warning and continue with those URLs.

FR-2.5. The tool SHALL reuse the `--timeout` value for all sitemap-related HTTP requests.

### FR-3. Sitemap Parsing

FR-3.1. The tool SHALL support the following sitemap formats:

| Format | Detection | Behavior |
|--------|-----------|----------|
| XML Sitemap (`<urlset>`) | Root element is `<urlset>` | Extract all `<loc>` values |
| Sitemap Index (`<sitemapindex>`) | Root element is `<sitemapindex>` | Extract child sitemap URLs from `<loc>` elements, then fetch and parse each recursively |
| Plain text sitemap | Content-Type is `text/plain` or file does not parse as XML | Treat each non-empty line as a URL |

FR-3.2. When a sitemap index is encountered, the tool SHALL recursively fetch and parse each referenced sitemap. Recursion SHALL be limited to a maximum depth of 2 (index → sitemap → URLs). If a nested sitemap is itself an index, the tool SHALL log a warning to stderr and skip it.

FR-3.3. XML parsing SHALL be namespace-aware. Sitemap elements use the namespace `http://www.sitemaps.org/schemas/sitemap/0.9`. The tool SHALL match elements by local name regardless of namespace prefix.

FR-3.4. The tool SHALL extract only `<loc>` elements. Other sitemap elements (`<lastmod>`, `<changefreq>`, `<priority>`) MAY be used in future versions but SHALL be ignored in this specification.

FR-3.5. If a sitemap file cannot be parsed (malformed XML, unexpected structure), the tool SHALL log a warning to stderr identifying the sitemap URL and continue processing any remaining sitemaps.

FR-3.6. All extracted `<loc>` values SHALL be validated using the same URL validation rules as positional arguments. Invalid URLs SHALL be skipped with a warning to stderr.

### FR-4. Scope Filtering

FR-4.1. By default, the tool SHALL only include URLs whose origin (scheme + host + port) matches the `--crawl` target origin. URLs pointing to different origins SHALL be silently excluded.

FR-4.2. The tool SHALL accept a `--crawl-allow-external` flag that disables origin filtering, allowing all valid URLs from the sitemap to be included.

FR-4.3. The tool MAY accept a `--crawl-pattern` option in a future version to filter URLs by glob or regex pattern. This specification does not define pattern filtering behavior.

### FR-5. Limits

FR-5.1. The tool SHALL accept a `--crawl-limit` (`-l`) option whose value is a positive integer specifying the maximum number of URLs to audit from the crawl. When the sitemap yields more URLs than the limit, the tool SHALL take the first N URLs in document order and discard the rest.

FR-5.2. When `--crawl-limit` is specified, the tool SHOULD print a message to stderr indicating how many URLs were discovered and how many will be audited (e.g., `Discovered 1,243 URLs, auditing first 50 (--crawl-limit)`).

FR-5.3. If `--crawl-limit` is not specified, the tool SHALL default to auditing all discovered URLs.

FR-5.4. The tool SHOULD print a warning to stderr when the discovered URL count exceeds 100 and no `--crawl-limit` is specified, informing the user that the run may take a while and suggesting `--crawl-limit`.

### FR-6. Integration with Batch Pipeline

FR-6.1. After sitemap discovery, parsing, scope filtering, and limit application, the resulting URL list SHALL be merged with any positional or `--file` URLs, then deduplicated per `SPEC-batch.md` FR-3.

FR-6.2. The merged URL list SHALL be passed to the existing batch pipeline (`run_batch`). All batch behavior — per-URL error handling, output formatting, exit codes, `--fail-under`, `--quiet` — SHALL apply unchanged.

FR-6.3. In single-URL mode (crawl discovers exactly one URL, no other sources), the tool SHALL route to the single-URL code path per `SPEC-batch.md` FR-1.6/NFR-1.1.

FR-6.4. Crawl-discovered URLs SHALL appear after positional URLs and before `--file` URLs in processing order.

---

## Output

### FR-7. Crawl Discovery Output

FR-7.1. Before batch processing begins, the tool SHOULD print a crawl summary to stderr (unless `--quiet` is active):

```
Crawl: found 3 sitemap(s) for https://example.com
Crawl: discovered 247 unique URLs
```

FR-7.2. In JSON output (`--format json`), the batch wrapper object SHALL include an additional key when `--crawl` was used:

| Key | Type | Description |
|-----|------|-------------|
| `crawl` | `object` | Crawl metadata (only present when `--crawl` is used) |

The `crawl` object SHALL have the following structure:

```json
{
  "origin": "https://example.com",
  "sitemaps_found": 3,
  "urls_discovered": 247,
  "urls_after_filter": 247,
  "urls_after_limit": 50
}
```

FR-7.3. In text and CSV output, crawl metadata SHALL NOT appear in the main output body. It is reported via stderr only (FR-7.1).

---

## Exit Codes

### FR-8. Exit Code Behavior

FR-8.1. Crawl mode SHALL use the same exit code semantics as batch mode (`SPEC-batch.md` FR-9).

FR-8.2. Sitemap discovery or parsing failures when `--crawl` is the sole input source SHALL exit with code 2 (input error).

FR-8.3. Sitemap discovery or parsing failures when other URL sources are present SHALL NOT alter the exit code — the batch proceeds with the remaining URLs.

---

## Non-Functional Requirements

### NFR-1. Backward Compatibility

NFR-1.1. When `--crawl` is not specified, the tool SHALL behave identically to its current behavior. No existing flags, defaults, or output formats SHALL change.

NFR-1.2. The `--crawl-limit` and `--crawl-allow-external` flags SHALL be ignored when `--crawl` is not specified.

### NFR-2. Performance

NFR-2.1. Sitemap fetching and parsing SHALL complete before any auditing begins. The tool SHALL NOT interleave sitemap discovery with URL auditing.

NFR-2.2. When fetching multiple sitemaps from a sitemap index, the tool SHALL fetch them sequentially to avoid overwhelming the target server. The tool MAY support concurrent sitemap fetching in a future version.

NFR-2.3. Sitemap responses SHOULD NOT be cached to disk. The tool SHALL hold parsed URL lists in memory.

NFR-2.4. For sitemap index files referencing a large number of child sitemaps, the tool SHALL impose a maximum of 50 child sitemaps. If the index references more than 50, the tool SHALL process only the first 50 and print a warning to stderr.

### NFR-3. Robustness

NFR-3.1. The tool SHALL NOT crash or produce a stack trace on malformed sitemaps, network errors during sitemap fetching, or unexpected content types. All such conditions SHALL produce a warning or error to stderr and be handled gracefully.

NFR-3.2. The tool SHALL handle gzip-compressed sitemaps (Content-Encoding: gzip) transparently, as this is common for large sitemaps. The underlying HTTP client (`httpx`) handles this by default.

NFR-3.3. The tool SHALL handle `.xml.gz` sitemap URLs referenced in robots.txt or sitemap index files. The tool SHALL fetch these URLs and rely on the HTTP client to decompress the response.

### NFR-4. Testability

NFR-4.1. Sitemap discovery logic (robots.txt parsing, fallback) SHALL be implemented as pure functions that accept fetched content and return sitemap URLs, testable without performing HTTP requests.

NFR-4.2. Sitemap parsing logic SHALL be implemented as pure functions that accept XML/text content and return URL lists, testable without performing HTTP requests.

NFR-4.3. Scope filtering and limit application SHALL be implemented as pure functions.

NFR-4.4. Integration with the batch pipeline SHALL be testable by injecting mock fetch functions.

### NFR-5. Maintainability

NFR-5.1. Crawl logic SHALL be implemented in a dedicated module (`crawl.py` or equivalent), separate from `cli.py` and `batch.py`.

NFR-5.2. The CLI module SHALL delegate to the crawl module when `--crawl` is specified, and pass the resulting URL list to the batch module.

NFR-5.3. The crawl module SHALL depend only on the project's existing `fetcher.py` module and Python standard library modules (`xml.etree.ElementTree`, `urllib.parse`, `typing`).

---

## CLI Interface Summary

```
botaudit --crawl https://example.com [options]
botaudit --crawl https://example.com --crawl-limit 50 --format json
botaudit --crawl https://example.com --crawl-allow-external
botaudit --crawl https://example.com https://example.com/extra-page --file more.txt
```

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--crawl` | | URL | — | Target origin for sitemap-based URL discovery |
| `--crawl-limit` | `-l` | int | unlimited | Maximum number of crawl-discovered URLs to audit |
| `--crawl-allow-external` | | flag | off | Include URLs from sitemaps that point to other origins |
