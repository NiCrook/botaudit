"""Page-type detection heuristics (SPEC-page-type-heuristics).

Classifies each analyzed page into a type (article, product, documentation,
listing, homepage, or generic) using a weighted vote system. Detection is
advisory — it does not alter scores or weights, only drives type-aware
recommendations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from botaudit.analysis import AnalysisResult


# FR-1.1: Supported page types.
PAGE_TYPES: frozenset[str] = frozenset({
    "article", "product", "documentation", "listing", "homepage", "generic",
})

# FR-2.3: Minimum cumulative vote to assign a non-generic type.
MIN_CONFIDENCE_THRESHOLD: float = 2.0

# FR-2.4.1: JSON-LD @type → (page_type, vote_weight).
JSONLD_TYPE_VOTES: dict[str, tuple[str, float]] = {
    "Article": ("article", 3.0),
    "NewsArticle": ("article", 3.0),
    "BlogPosting": ("article", 3.0),
    "Review": ("article", 3.0),
    "Product": ("product", 3.0),
    "Offer": ("product", 3.0),
    "AggregateRating": ("product", 3.0),
    "HowTo": ("documentation", 2.0),
    "Course": ("documentation", 2.0),
    "SoftwareApplication": ("documentation", 2.0),
    "FAQPage": ("documentation", 2.0),
    "ItemList": ("listing", 2.0),
    "CollectionPage": ("listing", 2.0),
    "BreadcrumbList": ("listing", 2.0),
    "WebSite": ("homepage", 1.5),
    "Organization": ("homepage", 1.5),
    "Event": ("article", 1.5),
    "Recipe": ("article", 1.5),
    "JobPosting": ("article", 1.5),
}

# FR-2.4.4: og:type value → (page_type, vote_weight).
OG_TYPE_VOTES: dict[str, tuple[str, float]] = {
    "article": ("article", 2.0),
    "product": ("product", 2.0),
    "product.item": ("product", 2.0),
    "website": ("homepage", 1.0),
}

# FR-2.4.6: URL path substrings → (page_type, vote_weight).
# Order matters — first matching group wins (FR-2.4.7).
URL_PATH_PATTERNS: list[tuple[list[str], str, float]] = [
    (["/blog/", "/post/", "/news/", "/article/"], "article", 1.5),
    (["/product/", "/item/", "/shop/", "/store/"], "product", 1.5),
    (
        ["/docs/", "/documentation/", "/guide/", "/tutorial/",
         "/reference/", "/api/"],
        "documentation",
        1.5,
    ),
    (["/category/", "/tag/", "/archive/", "/search", "/page/"], "listing", 1.5),
]

# FR-2.4.11: <meta name="pagetype"> value → page_type.
PAGETYPE_META_MAP: dict[str, str] = {
    "article": "article",
    "product": "product",
    "product.item": "product",
    "website": "homepage",
    "home": "homepage",
    "docs": "documentation",
    "documentation": "documentation",
    "category": "listing",
    "listing": "listing",
}


# ---------------------------------------------------------------------------
# Dataclasses (FR-10.1)
# ---------------------------------------------------------------------------

@dataclass
class PageTypeSignal:
    """A single signal contributing to page-type detection."""

    source: str      # "json_ld", "og_type", "url_path", "html_structure", "meta_tag"
    type_vote: str   # The page type this signal votes for
    weight: float    # Vote weight
    detail: str      # Human-readable explanation


@dataclass
class PageTypeResult:
    """Result of page-type detection for a single URL."""

    page_type: str = "generic"
    confidence: str = "none"  # "high", "medium", "low", "none", "override"
    signals: list[PageTypeSignal] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Detection (FR-2)
# ---------------------------------------------------------------------------

def _add_vote(
    votes: dict[str, float],
    signals: list[PageTypeSignal],
    source: str,
    page_type: str,
    weight: float,
    detail: str,
) -> None:
    """Record a signal and accumulate its vote."""
    signals.append(PageTypeSignal(source, page_type, weight, detail))
    votes[page_type] = votes.get(page_type, 0) + weight


def detect_page_type(
    analysis: AnalysisResult,
    url: str,
    *,
    html: str | None = None,
) -> PageTypeResult:
    """Detect the page type from analysis results, URL, and optional HTML.

    NFR-1.1: No additional HTTP requests — all data from existing analysis.
    FR-2.2: Highest cumulative vote wins; falls back to *generic*.
    """
    signals: list[PageTypeSignal] = []
    votes: dict[str, float] = {}

    # --- FR-2.4.1: JSON-LD @type signals ---
    jsonld_types: list[str] = [
        b.type_value
        for b in analysis.structured_data.json_ld_blocks
        if b.raw_valid and b.type_value
    ]
    # FR-2.4.3: BreadcrumbList only votes when it is the sole type.
    breadcrumb_only = (
        len(jsonld_types) == 1 and jsonld_types[0] == "BreadcrumbList"
    )
    for type_val in jsonld_types:
        if type_val not in JSONLD_TYPE_VOTES:
            continue
        if type_val == "BreadcrumbList" and not breadcrumb_only:
            continue
        pt, w = JSONLD_TYPE_VOTES[type_val]
        _add_vote(votes, signals, "json_ld", pt, w, f"@type: {type_val}")

    # Prepare soup for HTML-dependent signals
    soup: BeautifulSoup | None = None
    if html is not None:
        soup = BeautifulSoup(html, "html.parser")

    # --- FR-2.4.4: og:type signal ---
    if soup is not None:
        og_tag = soup.find("meta", attrs={"property": "og:type"})
        if og_tag:
            og_val = (og_tag.get("content", "") or "").strip().lower()
            if og_val in OG_TYPE_VOTES:
                pt, w = OG_TYPE_VOTES[og_val]
                _add_vote(votes, signals, "og_type", pt, w,
                          f"og:type={og_val}")

    # --- FR-2.4.6: URL path patterns ---
    parsed = urlparse(url)
    path = parsed.path.lower()
    if path in ("", "/", "/index.html", "/index.htm"):
        _add_vote(votes, signals, "url_path", "homepage", 2.0, "/")
    else:
        for substrings, pt, w in URL_PATH_PATTERNS:
            matched_sub = next((s for s in substrings if s in path), None)
            if matched_sub is not None:
                _add_vote(votes, signals, "url_path", pt, w, matched_sub)
                break  # first group wins

    # --- FR-2.4.8: HTML structure signals ---
    if soup is not None:
        _collect_html_signals(soup, analysis, votes, signals)
    else:
        # Fallback: use semantic_breakdown when raw HTML is unavailable.
        if "article" in analysis.semantic_html.semantic_breakdown:
            _add_vote(votes, signals, "html_structure", "article", 1.5,
                      "<article> element present")
        if "time" in analysis.semantic_html.semantic_breakdown:
            _add_vote(votes, signals, "html_structure", "article", 0.5,
                      "<time> element present")

    # --- FR-2.4.10: pagetype meta tag ---
    if soup is not None:
        pt_tag = (
            soup.find("meta", attrs={"name": re.compile(r"^pagetype$", re.I)})
            or soup.find("meta", attrs={"property": re.compile(r"^pagetype$", re.I)})
        )
        if pt_tag:
            pt_val = (pt_tag.get("content", "") or "").strip().lower()
            if pt_val in PAGETYPE_META_MAP:
                mapped = PAGETYPE_META_MAP[pt_val]
                _add_vote(votes, signals, "meta_tag", mapped, 2.0,
                          f'pagetype="{pt_val}"')

    # --- FR-2.2 / FR-2.3: Select winning type ---
    if not votes:
        return PageTypeResult("generic", "none", signals)

    best_type = max(votes, key=lambda k: votes[k])
    best_vote = votes[best_type]

    if best_vote < MIN_CONFIDENCE_THRESHOLD:
        return PageTypeResult("generic", "none", signals)

    # FR-3.1 / FR-3.2: Confidence level.
    total_votes = sum(votes.values())
    ratio = best_vote / total_votes if total_votes else 0

    if best_vote >= 4.0 and ratio >= 0.6:
        confidence = "high"
    elif best_vote >= 2.0 and ratio >= 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    return PageTypeResult(best_type, confidence, signals)


def _collect_html_signals(
    soup: BeautifulSoup,
    analysis: AnalysisResult,
    votes: dict[str, float],
    signals: list[PageTypeSignal],
) -> None:
    """Gather HTML-structure signals from the parsed document (FR-2.4.8)."""
    has_article = bool(soup.find("article"))
    if has_article:
        _add_vote(votes, signals, "html_structure", "article", 1.5,
                  "<article> element present")

    if soup.find("time"):
        _add_vote(votes, signals, "html_structure", "article", 0.5,
                  "<time> element present")

    word_count = analysis.content_availability.word_count
    if word_count > 500 and has_article:
        _add_vote(votes, signals, "html_structure", "article", 1.0,
                  "High word count with <article>")

    code_count = len(soup.find_all("code")) + len(soup.find_all("pre"))
    if code_count >= 3:
        _add_vote(votes, signals, "html_structure", "documentation", 1.5,
                  f"{code_count} <code>/<pre> elements")

    heading_count = len(soup.find_all("h2")) + len(soup.find_all("h3"))
    if heading_count >= 5 and code_count > 0:
        _add_vote(votes, signals, "html_structure", "documentation", 1.0,
                  f"{heading_count} headings with code blocks")

    if analysis.link_discoverability.navigable_links >= 10:
        li_with_links = len(soup.select("li a[href]"))
        if li_with_links >= 10:
            _add_vote(votes, signals, "html_structure", "listing", 1.0,
                      f"{li_with_links} list items with links")
