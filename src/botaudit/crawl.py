"""Sitemap crawl mode (SPEC-crawl).

NFR-5.1: Dedicated module, separate from cli.py and batch.py.
NFR-5.3: Depends only on fetcher.py + stdlib (xml.etree, urllib.parse, typing).
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from urllib.parse import urlparse

from botaudit.fetcher import DEFAULT_TIMEOUT, FetchError, fetch

# Sitemap XML namespace (FR-3.3)
_SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# NFR-2.4: Maximum child sitemaps to process from a sitemap index
_MAX_INDEX_CHILDREN = 50

# FR-3.2: Maximum recursion depth for sitemap indexes
_MAX_RECURSION_DEPTH = 2


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class CrawlResult:
    """Metadata about the crawl discovery phase (FR-7.2)."""

    origin: str
    sitemaps_found: int = 0
    urls_discovered: int = 0
    urls_after_filter: int = 0
    urls_after_limit: int = 0


# ---------------------------------------------------------------------------
# Sitemap discovery — FR-2
# NFR-4.1: Pure functions that accept fetched content and return URLs.
# ---------------------------------------------------------------------------

def parse_robots_sitemaps(robots_txt: str) -> list[str]:
    """Extract Sitemap: directive URLs from robots.txt content.

    FR-2.2: Case-insensitive directive matching.
    FR-2.3: Only absolute URLs are returned; relative URLs are skipped.

    Returns a list of sitemap URLs found.
    """
    sitemaps: list[str] = []
    for line in robots_txt.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            value = stripped[len("sitemap:"):].strip()
            # FR-2.3: only absolute URLs
            parsed = urlparse(value)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                sitemaps.append(value)
            elif value:
                print(
                    f"Warning: ignoring relative sitemap URL: {value}",
                    file=sys.stderr,
                )
    return sitemaps


def discover_sitemaps(
    origin: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[str]:
    """Discover sitemap URLs for a given origin.

    FR-2.1: Try robots.txt first, fall back to {origin}/sitemap.xml.
    FR-2.5: Uses the provided timeout for HTTP requests.

    Returns a list of sitemap URLs to fetch and parse.
    """
    # Normalize origin: strip trailing slash
    origin = origin.rstrip("/")

    # Step 1: try robots.txt
    robots_url = f"{origin}/robots.txt"
    try:
        robots_content = fetch(robots_url, timeout=timeout)
        sitemaps = parse_robots_sitemaps(robots_content)
        if sitemaps:
            return sitemaps
    except FetchError:
        pass  # Fall through to default location

    # Step 2: fall back to /sitemap.xml
    return [f"{origin}/sitemap.xml"]


# ---------------------------------------------------------------------------
# Sitemap parsing — FR-3
# NFR-4.2: Pure functions that accept content and return URL lists.
# ---------------------------------------------------------------------------

def parse_sitemap_xml(content: str) -> tuple[list[str], list[str]]:
    """Parse an XML sitemap or sitemap index.

    FR-3.1: Detects <urlset> vs <sitemapindex> by root element.
    FR-3.3: Namespace-aware element matching.
    FR-3.4: Extracts only <loc> elements.

    Returns (page_urls, child_sitemap_urls).
    - For a <urlset>: page_urls populated, child_sitemap_urls empty.
    - For a <sitemapindex>: page_urls empty, child_sitemap_urls populated.
    """
    root = ET.fromstring(content)
    # Strip namespace from tag for comparison
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    if tag == "sitemapindex":
        children: list[str] = []
        for loc in root.iter(f"{{{_SITEMAP_NS}}}loc"):
            if loc.text and loc.text.strip():
                children.append(loc.text.strip())
        # Also try without namespace for non-conforming sitemaps
        if not children:
            for loc in root.iter("loc"):
                if loc.text and loc.text.strip():
                    children.append(loc.text.strip())
        return [], children

    # Default: treat as <urlset>
    pages: list[str] = []
    for loc in root.iter(f"{{{_SITEMAP_NS}}}loc"):
        if loc.text and loc.text.strip():
            pages.append(loc.text.strip())
    # Also try without namespace for non-conforming sitemaps
    if not pages:
        for loc in root.iter("loc"):
            if loc.text and loc.text.strip():
                pages.append(loc.text.strip())
    return pages, []


def parse_sitemap_text(content: str) -> list[str]:
    """Parse a plain-text sitemap (one URL per line).

    FR-3.1: Fallback for non-XML sitemaps.

    Returns a list of URL strings.
    """
    urls: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            urls.append(stripped)
    return urls


def _validate_url(url: str) -> bool:
    """Check if a URL has a valid http(s) scheme and netloc."""
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def fetch_and_parse_sitemap(
    sitemap_url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    depth: int = 0,
) -> list[str]:
    """Fetch a sitemap URL and recursively extract page URLs.

    FR-3.1: Handles XML sitemaps, sitemap indexes, and plain text.
    FR-3.2: Recursive depth limited to _MAX_RECURSION_DEPTH.
    FR-3.5: Logs warnings to stderr for parse failures; does not raise.
    FR-3.6: Validates extracted URLs; skips invalid ones with a warning.
    NFR-2.4: Limits child sitemaps to _MAX_INDEX_CHILDREN.

    Returns a list of page URLs discovered from this sitemap (and children).
    """
    try:
        content = fetch(sitemap_url, timeout=timeout)
    except FetchError as exc:
        print(
            f"Warning: could not fetch sitemap {sitemap_url}: {exc}",
            file=sys.stderr,
        )
        return []

    # Try XML first, fall back to plain text
    page_urls: list[str] = []
    child_sitemaps: list[str] = []

    try:
        page_urls, child_sitemaps = parse_sitemap_xml(content)
    except ET.ParseError:
        # FR-3.1: plain text fallback
        page_urls = parse_sitemap_text(content)

    # FR-3.6: validate extracted page URLs
    valid_pages: list[str] = []
    for url in page_urls:
        if _validate_url(url):
            valid_pages.append(url)
        else:
            print(
                f"Warning: skipping invalid URL in sitemap: {url}",
                file=sys.stderr,
            )

    # FR-3.2: recurse into child sitemaps if within depth limit
    if child_sitemaps and depth >= _MAX_RECURSION_DEPTH:
        print(
            f"Warning: sitemap index recursion limit reached at {sitemap_url}, "
            f"skipping {len(child_sitemaps)} nested sitemap(s).",
            file=sys.stderr,
        )
        return valid_pages

    # NFR-2.4: cap child sitemaps
    if len(child_sitemaps) > _MAX_INDEX_CHILDREN:
        print(
            f"Warning: sitemap index has {len(child_sitemaps)} children, "
            f"processing only first {_MAX_INDEX_CHILDREN}.",
            file=sys.stderr,
        )
        child_sitemaps = child_sitemaps[:_MAX_INDEX_CHILDREN]

    # NFR-2.2: fetch children sequentially
    for child_url in child_sitemaps:
        valid_pages.extend(
            fetch_and_parse_sitemap(
                child_url,
                timeout=timeout,
                depth=depth + 1,
            )
        )

    return valid_pages


# ---------------------------------------------------------------------------
# Scope filtering — FR-4
# NFR-4.3: Pure function.
# ---------------------------------------------------------------------------

def _get_origin(url: str) -> tuple[str, str, int]:
    """Extract (scheme, host, port) from a URL for origin comparison."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = parsed.hostname or ""
    host = host.lower()
    port = parsed.port
    if port is None:
        port = 443 if scheme == "https" else 80
    return (scheme, host, port)


def filter_by_origin(urls: list[str], origin: str) -> list[str]:
    """Keep only URLs whose origin matches the target.

    FR-4.1: Compares scheme + host + port.

    Returns filtered list in original order.
    """
    target = _get_origin(origin)
    return [url for url in urls if _get_origin(url) == target]


# ---------------------------------------------------------------------------
# Limit application — FR-5
# NFR-4.3: Pure function.
# ---------------------------------------------------------------------------

def apply_limit(
    urls: list[str],
    limit: int | None,
    *,
    quiet: bool = False,
) -> list[str]:
    """Apply --crawl-limit to the URL list.

    FR-5.1: Take first N URLs in document order.
    FR-5.2: Print discovery/limit message to stderr.
    FR-5.3: No limit → return all.
    FR-5.4: Warn if >100 URLs and no limit.

    Returns the (possibly truncated) list.
    """
    total = len(urls)

    if limit is not None and total > limit:
        if not quiet:
            print(
                f"Discovered {total} URLs, auditing first {limit} "
                f"(--crawl-limit)",
                file=sys.stderr,
            )
        return urls[:limit]

    # FR-5.4: warn if large and no limit
    if total > 100 and limit is None and not quiet:
        print(
            f"Warning: {total} URLs discovered — this may take a while. "
            f"Consider using --crawl-limit to cap the batch.",
            file=sys.stderr,
        )

    return urls


# ---------------------------------------------------------------------------
# Top-level orchestrator — FR-6
# ---------------------------------------------------------------------------

def crawl(
    origin: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    limit: int | None = None,
    allow_external: bool = False,
    quiet: bool = False,
) -> tuple[list[str], CrawlResult]:
    """Run the full crawl discovery pipeline.

    FR-2 → FR-5: Discover sitemaps → parse → filter → limit.
    FR-7.1: Print crawl summary to stderr (unless quiet).

    Returns (urls, crawl_metadata).
    """
    meta = CrawlResult(origin=origin)

    # FR-2: discover sitemaps
    sitemap_urls = discover_sitemaps(origin, timeout=timeout)
    meta.sitemaps_found = len(sitemap_urls)

    if not quiet:
        print(
            f"Crawl: found {meta.sitemaps_found} sitemap(s) for {origin}",
            file=sys.stderr,
        )

    # FR-3: fetch and parse all sitemaps
    all_urls: list[str] = []
    for sitemap_url in sitemap_urls:
        all_urls.extend(
            fetch_and_parse_sitemap(sitemap_url, timeout=timeout)
        )

    # Deduplicate (order-preserving)
    seen: set[str] = set()
    unique: list[str] = []
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    meta.urls_discovered = len(unique)

    if not quiet:
        print(
            f"Crawl: discovered {meta.urls_discovered} unique URLs",
            file=sys.stderr,
        )

    # FR-4: scope filtering
    if allow_external:
        filtered = unique
    else:
        filtered = filter_by_origin(unique, origin)
    meta.urls_after_filter = len(filtered)

    # FR-5: apply limit
    limited = apply_limit(filtered, limit, quiet=quiet)
    meta.urls_after_limit = len(limited)

    return limited, meta
