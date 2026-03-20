"""Section 3 — Analysis of HTML documents for AI accessibility."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Comment

# 3.1.1 — Semantic elements list
SEMANTIC_ELEMENTS = frozenset({
    "nav", "main", "article", "section", "header", "footer", "aside",
    "table", "form", "ul", "ol", "figure", "figcaption", "details",
    "summary", "time", "mark", "address",
})

# 3.1.2 — Generic container elements
GENERIC_CONTAINERS = frozenset({"div", "span"})

# 3.3.2 — Patterns for non-navigable links
_NON_NAVIGABLE_RE = re.compile(r"^(?:javascript:|#$|$)")


# --- Result dataclasses ---


@dataclass
class SemanticHTMLResult:
    """3.1 — Semantic HTML analysis."""

    semantic_count: int = 0
    generic_count: int = 0
    semantic_ratio: float = 0.0
    semantic_breakdown: dict[str, int] = field(default_factory=dict)


@dataclass
class ContentAvailabilityResult:
    """3.2 — Content availability analysis."""

    visible_text: str = ""
    word_count: int = 0
    char_count: int = 0
    has_meaningful_content: bool = False
    has_noscript: bool = False
    noscript_text: str = ""


@dataclass
class LinkDiscoverabilityResult:
    """3.3 — Link discoverability analysis."""

    total_links: int = 0
    navigable_links: int = 0
    non_navigable_links: int = 0
    navigable_ratio: float = 0.0


@dataclass
class StructuredDataResult:
    """3.4 — Structured data analysis."""

    has_json_ld: bool = False
    json_ld_count: int = 0
    has_open_graph: bool = False
    open_graph_tags: list[str] = field(default_factory=list)
    has_meta_description: bool = False
    meta_description: str = ""


@dataclass
class MetadataResult:
    """3.5 — Metadata and discoverability analysis."""

    has_title: bool = False
    title: str = ""
    has_canonical: bool = False
    canonical_url: str = ""
    has_sitemap_ref: bool = False
    has_robots_meta: bool = False
    robots_directives: str = ""


@dataclass
class AnalysisResult:
    """Combined results from all analysis categories."""

    semantic_html: SemanticHTMLResult
    content_availability: ContentAvailabilityResult
    link_discoverability: LinkDiscoverabilityResult
    structured_data: StructuredDataResult
    metadata: MetadataResult
    llm_discovery: object | None = None  # LLMDiscoverabilityResult when present


# --- Analyzers ---


def analyze_semantic_html(soup: BeautifulSoup) -> SemanticHTMLResult:
    """3.1 — Count semantic vs generic elements and compute ratio."""
    result = SemanticHTMLResult()

    # 3.1.1 — Count semantic elements
    for tag_name in SEMANTIC_ELEMENTS:
        count = len(soup.find_all(tag_name))
        if count:
            result.semantic_breakdown[tag_name] = count
            result.semantic_count += count

    # 3.1.2 — Count generic containers
    for tag_name in GENERIC_CONTAINERS:
        result.generic_count += len(soup.find_all(tag_name))

    # 3.1.3 — Compute ratio (semantic / total)
    total = result.semantic_count + result.generic_count
    if total > 0:
        result.semantic_ratio = result.semantic_count / total

    # 3.1.4 — Ratio is what matters; no penalty for few elements

    return result


def analyze_content_availability(soup: BeautifulSoup) -> ContentAvailabilityResult:
    """3.2 — Extract visible text and determine if content is meaningful."""
    result = ContentAvailabilityResult()

    # 3.2.1 — Extract visible text (strip scripts, styles, comments)
    for element in soup.find_all(["script", "style"]):
        element.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    text = soup.get_text(separator=" ", strip=True)
    result.visible_text = text

    # 3.2.3 — Measure visible text
    result.char_count = len(text)
    result.word_count = len(text.split()) if text else 0

    # 3.2.2 — Determine if meaningful content exists
    # An empty shell typically has very few words of actual content
    result.has_meaningful_content = result.word_count > 10

    # 3.2.4 — Check for <noscript> fallback
    noscript = soup.find("noscript")
    if noscript:
        result.has_noscript = True
        result.noscript_text = noscript.get_text(strip=True)

    return result


def analyze_link_discoverability(soup: BeautifulSoup) -> LinkDiscoverabilityResult:
    """3.3 — Count and classify links."""
    result = LinkDiscoverabilityResult()

    # 3.3.1 — Count <a> elements with href
    links = soup.find_all("a", href=True)
    result.total_links = len(links)

    # 3.3.2 — Distinguish navigable vs non-navigable
    for link in links:
        href = link["href"].strip()
        if _NON_NAVIGABLE_RE.match(href):
            result.non_navigable_links += 1
        else:
            result.navigable_links += 1

    # 3.3.3 — Ratio of navigable to total
    if result.total_links > 0:
        result.navigable_ratio = result.navigable_links / result.total_links

    return result


def analyze_structured_data(soup: BeautifulSoup) -> StructuredDataResult:
    """3.4 — Check for JSON-LD, Open Graph, and meta description."""
    result = StructuredDataResult()

    # 3.4.1 — JSON-LD
    json_ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    result.json_ld_count = len(json_ld_scripts)
    result.has_json_ld = result.json_ld_count > 0

    # 3.4.2 — Open Graph meta tags
    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
    result.has_open_graph = len(og_tags) > 0
    result.open_graph_tags = [tag.get("property", "") for tag in og_tags]

    # 3.4.3 — Meta description
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_desc and meta_desc.get("content", "").strip():
        result.has_meta_description = True
        result.meta_description = meta_desc["content"].strip()

    return result


def analyze_metadata(soup: BeautifulSoup) -> MetadataResult:
    """3.5 — Check title, canonical, sitemap ref, and robots meta."""
    result = MetadataResult()

    # 3.5.1 — <title> with non-empty content
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        result.has_title = True
        result.title = title_tag.get_text(strip=True)

    # 3.5.2 — Canonical URL
    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href", "").strip():
        result.has_canonical = True
        result.canonical_url = canonical["href"].strip()

    # 3.5.3 — Sitemap reference (HTML only per 3.5.5)
    sitemap = soup.find("link", attrs={"rel": "sitemap"})
    result.has_sitemap_ref = sitemap is not None

    # 3.5.4 — Robots meta tag
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if robots and robots.get("content", "").strip():
        result.has_robots_meta = True
        result.robots_directives = robots["content"].strip()

    return result


def analyze(html: str) -> AnalysisResult:
    """Run all Section 3 analyses on raw HTML and return combined results.

    Note: content_availability calls decompose() on script/style tags,
    so it must use its own soup copy. Other analyzers share the original.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Content analysis mutates the tree (removes scripts/styles),
    # so give it a separate copy.
    content_soup = BeautifulSoup(html, "html.parser")

    return AnalysisResult(
        semantic_html=analyze_semantic_html(soup),
        content_availability=analyze_content_availability(content_soup),
        link_discoverability=analyze_link_discoverability(soup),
        structured_data=analyze_structured_data(soup),
        metadata=analyze_metadata(soup),
    )
