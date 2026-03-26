"""Section 3 — Analysis of HTML documents for AI accessibility."""

from __future__ import annotations

import json as json_mod
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

# SPEC-structured-data-validation FR-1.3.2 — Recognized schema.org types.
RECOGNIZED_SCHEMA_TYPES: frozenset[str] = frozenset({
    "Article", "NewsArticle", "BlogPosting", "WebPage", "WebSite",
    "Organization", "LocalBusiness", "Person", "Product", "Offer",
    "BreadcrumbList", "FAQPage", "HowTo", "Event", "Recipe",
    "VideoObject", "ImageObject", "ItemList", "CollectionPage",
    "SearchAction", "SiteNavigationElement", "SoftwareApplication",
    "Course", "Review", "AggregateRating", "MedicalEntity", "JobPosting",
    "CreativeWork",
})

# SPEC-structured-data-validation FR-1.4.1 — Minimum recommended properties per type.
SCHEMA_MIN_PROPERTIES: dict[str, list[str]] = {
    "Article": ["headline", "author", "datePublished"],
    "NewsArticle": ["headline", "author", "datePublished"],
    "BlogPosting": ["headline", "author", "datePublished"],
    "WebSite": ["name", "url"],
    "WebPage": ["name", "url"],
    "Organization": ["name", "url"],
    "LocalBusiness": ["name", "address"],
    "Person": ["name"],
    "Product": ["name", "description"],
    "Offer": ["price", "priceCurrency"],
    "BreadcrumbList": ["itemListElement"],
    "FAQPage": ["mainEntity"],
    "HowTo": ["name", "step"],
    "Event": ["name", "startDate"],
    "Recipe": ["name", "recipeIngredient"],
    "VideoObject": ["name", "uploadDate"],
    "JobPosting": ["title", "datePosted"],
    "SoftwareApplication": ["name", "operatingSystem"],
    "Course": ["name", "provider"],
    "Review": ["itemReviewed", "author"],
}

# SPEC-structured-data-validation FR-2.1.1 — Required OG properties.
OG_REQUIRED: list[str] = ["og:title", "og:type", "og:image", "og:url"]

# SPEC-structured-data-validation FR-2.2.1 — Recommended OG properties.
OG_RECOMMENDED: list[str] = ["og:description", "og:site_name"]


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
class JsonLdBlock:
    """Validation result for a single JSON-LD block (FR-11.2)."""

    raw_valid: bool = False
    context_present: bool = False
    type_value: str = ""
    recognized_type: bool = False
    properties_present: list[str] = field(default_factory=list)
    properties_missing: list[str] = field(default_factory=list)


@dataclass
class StructuredDataResult:
    """3.4 — Structured data analysis."""

    # Existing fields (preserved)
    has_json_ld: bool = False
    json_ld_count: int = 0
    has_open_graph: bool = False
    open_graph_tags: list[str] = field(default_factory=list)
    has_meta_description: bool = False
    meta_description: str = ""

    # JSON-LD validation (FR-11.1)
    json_ld_parseable_count: int = 0
    json_ld_blocks: list[JsonLdBlock] = field(default_factory=list)

    # Open Graph validation (FR-11.1)
    og_required_present: list[str] = field(default_factory=list)
    og_required_missing: list[str] = field(default_factory=list)
    og_recommended_present: list[str] = field(default_factory=list)
    og_recommended_missing: list[str] = field(default_factory=list)

    # Meta description length (FR-11.1)
    meta_description_length: int = 0
    meta_description_length_class: str = ""

    # Twitter Cards (FR-11.1)
    has_twitter_cards: bool = False
    twitter_card_tags: list[str] = field(default_factory=list)

    # Microdata (FR-11.1)
    has_microdata: bool = False
    microdata_count: int = 0
    microdata_types: list[str] = field(default_factory=list)


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


def _is_schema_context(ctx: object) -> bool:
    """Check whether a @context value references schema.org (FR-1.2.2)."""
    if isinstance(ctx, str):
        return ctx.rstrip("/") in ("https://schema.org", "http://schema.org")
    if isinstance(ctx, list):
        return any(_is_schema_context(item) for item in ctx)
    if isinstance(ctx, dict):
        return any(_is_schema_context(v) for v in ctx.values())
    return False


def _validate_json_ld_object(obj: dict) -> JsonLdBlock:
    """Validate a single JSON-LD typed object (FR-1.2–1.4)."""
    block = JsonLdBlock(raw_valid=True)

    # FR-1.2 — @context
    block.context_present = _is_schema_context(obj.get("@context"))

    # FR-1.3 — @type
    type_val = obj.get("@type", "")
    if isinstance(type_val, list):
        type_val = type_val[0] if type_val else ""
    block.type_value = str(type_val)
    block.recognized_type = block.type_value in RECOGNIZED_SCHEMA_TYPES

    # FR-1.4 — Minimum recommended properties
    required = SCHEMA_MIN_PROPERTIES.get(block.type_value, [])
    for prop in required:
        val = obj.get(prop)
        if val is not None and val != "" and val != []:
            block.properties_present.append(prop)
        else:
            block.properties_missing.append(prop)

    return block


def _extract_typed_objects(data: object) -> list[dict]:
    """Extract all typed JSON-LD objects from parsed JSON (FR-1.1.3)."""
    objects: list[dict] = []
    if isinstance(data, dict):
        if "@type" in data:
            objects.append(data)
        if "@graph" in data and isinstance(data["@graph"], list):
            for item in data["@graph"]:
                if isinstance(item, dict) and "@type" in item:
                    # Propagate @context from parent if child lacks it
                    if "@context" not in item and "@context" in data:
                        item = {**item, "@context": data["@context"]}
                    objects.append(item)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "@type" in item:
                objects.append(item)
    return objects


def analyze_structured_data(soup: BeautifulSoup) -> StructuredDataResult:
    """3.4 — Check for JSON-LD, Open Graph, meta description, Twitter Cards, and microdata."""
    result = StructuredDataResult()

    # --- JSON-LD (FR-1) ---
    json_ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    result.json_ld_count = len(json_ld_scripts)
    result.has_json_ld = result.json_ld_count > 0

    for script in json_ld_scripts:
        text = script.string or ""
        try:
            data = json_mod.loads(text)
        except (json_mod.JSONDecodeError, ValueError):
            # FR-1.1.2 — present but unparseable
            result.json_ld_blocks.append(JsonLdBlock(raw_valid=False))
            continue
        result.json_ld_parseable_count += 1
        typed_objs = _extract_typed_objects(data)
        if typed_objs:
            for obj in typed_objs:
                result.json_ld_blocks.append(_validate_json_ld_object(obj))
        else:
            # Parseable but no typed objects
            result.json_ld_blocks.append(JsonLdBlock(raw_valid=True))

    # --- Open Graph (FR-2) ---
    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
    result.has_open_graph = len(og_tags) > 0
    result.open_graph_tags = [tag.get("property", "") for tag in og_tags]

    # Build set of OG properties with non-empty content (FR-2.1.2)
    og_present_set: set[str] = set()
    for tag in og_tags:
        prop = tag.get("property", "")
        content = tag.get("content", "")
        if prop and content and content.strip():
            og_present_set.add(prop)

    result.og_required_present = [p for p in OG_REQUIRED if p in og_present_set]
    result.og_required_missing = [p for p in OG_REQUIRED if p not in og_present_set]
    result.og_recommended_present = [p for p in OG_RECOMMENDED if p in og_present_set]
    result.og_recommended_missing = [p for p in OG_RECOMMENDED if p not in og_present_set]

    # --- Meta description (FR-3) ---
    meta_desc = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    if meta_desc and meta_desc.get("content", "").strip():
        result.has_meta_description = True
        result.meta_description = meta_desc["content"].strip()
        result.meta_description_length = len(result.meta_description)
        if result.meta_description_length < 50:
            result.meta_description_length_class = "too_short"
        elif result.meta_description_length <= 160:
            result.meta_description_length_class = "optimal"
        else:
            result.meta_description_length_class = "too_long"

    # --- Twitter Cards (FR-5) ---
    twitter_name = soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")})
    twitter_prop = soup.find_all("meta", attrs={"property": re.compile(r"^twitter:")})
    twitter_all = {id(t): t for t in [*twitter_name, *twitter_prop]}  # dedupe
    for tag in twitter_all.values():
        prop = tag.get("name") or tag.get("property", "")
        content = tag.get("content", "")
        if prop and content and content.strip():
            result.twitter_card_tags.append(prop)
    result.has_twitter_cards = len(result.twitter_card_tags) > 0

    # --- Microdata (FR-6) ---
    itemscopes = soup.find_all(attrs={"itemscope": True})
    result.microdata_count = len(itemscopes)
    result.has_microdata = result.microdata_count > 0
    for el in itemscopes:
        itemtype = el.get("itemtype", "")
        if itemtype:
            result.microdata_types.append(itemtype)

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
