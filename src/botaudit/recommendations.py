"""Section 7 — Recommendation engine for AI accessibility improvements.

7.1  Generate actionable recommendations per category when score < 90.
7.3  Order by severity (high → medium → low).
7.4  Per-category recommendation rules.
7.5  One pure function per category, extensible without modifying core logic.
SPEC-page-type-heuristics FR-4: Type-aware recommendations.
"""

from __future__ import annotations

from botaudit.analysis import (
    SEMANTIC_ELEMENTS,
    AnalysisResult,
    ContentAvailabilityResult,
    LinkDiscoverabilityResult,
    MetadataResult,
    SemanticHTMLResult,
    StructuredDataResult,
)
from botaudit.llm_discoverability import LLMDiscoverabilityResult
from botaudit.models import (
    CATEGORY_WEIGHTS,
    RECOMMENDATION_THRESHOLD,
    CategoryResult,
    Recommendation,
    Severity,
)
from botaudit.page_type import PageTypeResult

# §7.4.1.3 — Suggested contexts for absent semantic elements.
_SEMANTIC_SUGGESTIONS: dict[str, str] = {
    "article": "Wrap distinct content items (blog posts, cards, listings) in <article>.",
    "section": "Divide the page into thematic groups with <section>.",
    "aside": "Mark supplementary content (sidebars, promos) with <aside>.",
    "nav": "Wrap navigation link groups in <nav>.",
    "ul": "Convert sequences of sibling elements into <ul> lists.",
    "ol": "Use <ol> for ordered sequences (rankings, steps).",
    "time": "Mark up dates and times with <time datetime=\"...\">.",
    "address": "Wrap contact information in <address>.",
    "details": "Replace JS-toggled collapsible panels with <details>/<summary>.",
    "summary": "Pair <summary> with <details> for native disclosure widgets.",
    "figure": "Wrap images, diagrams, and captions in <figure>/<figcaption>.",
    "figcaption": "Add <figcaption> inside <figure> elements to label visual content.",
    "header": "Use <header> for introductory content or a group of navigational aids.",
    "footer": "Use <footer> for page or section footer content.",
    "main": "Wrap the primary content area in <main>.",
    "table": "Use <table> for tabular data instead of CSS grid layouts.",
    "form": "Wrap interactive inputs in <form> elements.",
    "mark": "Use <mark> to highlight search terms or key phrases.",
}


# --- Per-category recommenders (§7.4) ---


def recommend_semantic_html(result: SemanticHTMLResult) -> list[Recommendation]:
    """§7.4.1 — Semantic HTML recommendations."""
    recs: list[Recommendation] = []
    cat = "Semantic HTML"

    # §7.4.1.1 — Low semantic ratio
    if result.semantic_ratio < 0.50:
        total_generic = result.generic_count
        recs.append(Recommendation(
            message=(
                f"{total_generic} generic containers (<div>/<span>) found - "
                f"replace content wrappers with semantic elements like "
                f"<article>, <section>, <aside>, or <nav>."
            ),
            severity=Severity.HIGH,
            category=cat,
        ))

    # §7.4.1.2 — Missing semantic elements
    present = set(result.semantic_breakdown.keys())
    absent = SEMANTIC_ELEMENTS - present

    # §7.4.1.3 — Suggest specific substitutions for absent elements
    for tag in sorted(absent):
        suggestion = _SEMANTIC_SUGGESTIONS.get(tag)
        if suggestion:
            recs.append(Recommendation(
                message=suggestion,
                severity=Severity.MEDIUM,
                category=cat,
            ))

    return recs


def recommend_content_availability(
    result: ContentAvailabilityResult,
) -> list[Recommendation]:
    """§7.4.2 — Content availability recommendations."""
    recs: list[Recommendation] = []
    cat = "Content Availability"

    # §7.4.2.1 — Empty shell
    if not result.has_meaningful_content:
        recs.append(Recommendation(
            message=(
                "Page appears to be an empty shell — use server-side rendering "
                "or static HTML generation so AI clients receive real content."
            ),
            severity=Severity.HIGH,
            category=cat,
        ))

    # §7.4.2.2 — Low word count
    elif result.word_count < 100:
        recs.append(Recommendation(
            message=(
                f"Only {result.word_count} words in the initial HTML response — "
                f"render more content server-side to improve AI readability."
            ),
            severity=Severity.MEDIUM,
            category=cat,
        ))

    # §7.4.2.3 — Missing <noscript>
    if not result.has_noscript:
        recs.append(Recommendation(
            message="Add <noscript> content as a fallback for non-JS clients.",
            severity=Severity.LOW,
            category=cat,
        ))

    return recs


def recommend_link_discoverability(
    result: LinkDiscoverabilityResult,
) -> list[Recommendation]:
    """§7.4.3 — Link discoverability recommendations."""
    recs: list[Recommendation] = []
    cat = "Link Discoverability"

    # §7.4.3.2 — No links at all
    if result.total_links == 0:
        recs.append(Recommendation(
            message=(
                "No links found — add navigable <a href> links "
                "to enable crawling and content discovery."
            ),
            severity=Severity.HIGH,
            category=cat,
        ))
        return recs

    # §7.4.3.1 / §7.4.3.3 — Non-navigable links
    if result.non_navigable_links > 0:
        recs.append(Recommendation(
            message=(
                f"{result.non_navigable_links} non-navigable links found "
                f"(javascript:, href=\"#\", or empty) — replace with real URLs."
            ),
            severity=Severity.MEDIUM,
            category=cat,
        ))

    return recs


def recommend_structured_data(result: StructuredDataResult) -> list[Recommendation]:
    """§7.4.4 / SPEC-structured-data-validation FR-8 — Structured data recommendations."""
    recs: list[Recommendation] = []
    cat = "Structured Data"

    # FR-8.1 — Missing JSON-LD
    if not result.has_json_ld:
        recs.append(Recommendation(
            message=(
                "Add a JSON-LD block (<script type=\"application/ld+json\">) "
                "with at minimum @type and name properties."
            ),
            severity=Severity.HIGH,
            category=cat,
        ))
    else:
        # FR-8.2 — Unparseable JSON-LD
        unparseable = [b for b in result.json_ld_blocks if not b.raw_valid]
        if unparseable:
            recs.append(Recommendation(
                message=(
                    f"{len(unparseable)} JSON-LD block(s) contain invalid JSON "
                    f"— fix the syntax errors."
                ),
                severity=Severity.HIGH,
                category=cat,
            ))

        # FR-8.3 — Missing @context
        parseable = [b for b in result.json_ld_blocks if b.raw_valid]
        if parseable and not any(b.context_present for b in parseable):
            recs.append(Recommendation(
                message=(
                    'Add "@context": "https://schema.org" to JSON-LD blocks.'
                ),
                severity=Severity.MEDIUM,
                category=cat,
            ))

        # FR-8.4 — Missing minimum recommended properties
        for b in result.json_ld_blocks:
            if b.raw_valid and b.type_value and b.properties_missing:
                recs.append(Recommendation(
                    message=(
                        f"{b.type_value} is missing recommended properties: "
                        f"{', '.join(b.properties_missing)}."
                    ),
                    severity=Severity.MEDIUM,
                    category=cat,
                ))

    # FR-8.5 — Missing Open Graph
    if not result.has_open_graph:
        recs.append(Recommendation(
            message=(
                "Add Open Graph meta tags: og:title, og:type, "
                "og:image, and og:url."
            ),
            severity=Severity.MEDIUM,
            category=cat,
        ))
    # FR-8.6 — OG present but missing required properties
    elif result.og_required_missing:
        recs.append(Recommendation(
            message=(
                "Open Graph is missing required properties: "
                f"{', '.join(result.og_required_missing)}."
            ),
            severity=Severity.MEDIUM,
            category=cat,
        ))

    # FR-8.7 — Missing meta description
    if not result.has_meta_description:
        recs.append(Recommendation(
            message="Add a <meta name=\"description\"> tag.",
            severity=Severity.MEDIUM,
            category=cat,
        ))
    # FR-8.8 — Sub-optimal meta description length
    elif result.meta_description_length_class in ("too_short", "too_long"):
        if result.meta_description_length_class == "too_short":
            recs.append(Recommendation(
                message=(
                    f"Meta description is only {result.meta_description_length} characters "
                    f"— aim for 50–160 characters."
                ),
                severity=Severity.LOW,
                category=cat,
            ))
        else:
            recs.append(Recommendation(
                message=(
                    f"Meta description is {result.meta_description_length} characters "
                    f"— consider trimming to 160 characters or fewer."
                ),
                severity=Severity.LOW,
                category=cat,
            ))

    # FR-8.9 — Fewer than 2 structured data formats
    format_count = sum([
        result.json_ld_parseable_count > 0,
        result.has_open_graph,
        result.has_microdata,
        result.has_twitter_cards,
    ])
    if format_count < 2:
        recs.append(Recommendation(
            message=(
                "Only one structured data format detected — adding a second format "
                "(e.g., Open Graph, JSON-LD, or Twitter Cards) improves AI discoverability."
            ),
            severity=Severity.LOW,
            category=cat,
        ))

    return recs


def recommend_metadata(result: MetadataResult) -> list[Recommendation]:
    """§7.4.5 — Metadata & discoverability recommendations."""
    recs: list[Recommendation] = []
    cat = "Metadata & Discoverability"

    # §7.4.5.1 — Missing title
    if not result.has_title:
        recs.append(Recommendation(
            message="Add a descriptive <title> element.",
            severity=Severity.HIGH,
            category=cat,
        ))

    # §7.4.5.2 — Missing canonical
    if not result.has_canonical:
        recs.append(Recommendation(
            message="Add a <link rel=\"canonical\"> tag to declare the preferred URL.",
            severity=Severity.MEDIUM,
            category=cat,
        ))

    # §7.4.5.3 — Missing sitemap ref
    if not result.has_sitemap_ref:
        recs.append(Recommendation(
            message="Add a <link rel=\"sitemap\"> tag pointing to the XML sitemap.",
            severity=Severity.LOW,
            category=cat,
        ))

    # §7.4.5.4 — Missing robots meta
    if not result.has_robots_meta:
        recs.append(Recommendation(
            message="Add a <meta name=\"robots\"> tag with appropriate directives.",
            severity=Severity.LOW,
            category=cat,
        ))

    return recs


def recommend_llm_discovery(
    result: LLMDiscoverabilityResult,
) -> list[Recommendation]:
    """FR-9 — Generate recommendations for LLM Discoverability.

    FR-9.1: Only called when category scores < 90 (handled by caller).
    """
    recs: list[Recommendation] = []
    cat = "LLM Discoverability"

    # FR-9.2 — Restrictive: review AI crawler access (HIGH)
    if result.robots.classification == "restrictive":
        agents = ", ".join(result.robots.blocked_agents)
        recs.append(
            Recommendation(
                message=(
                    f"robots.txt blocks all known AI crawlers ({agents}). "
                    f"Review AI crawler access policies."
                ),
                severity=Severity.HIGH,
                category=cat,
            )
        )
    # FR-9.3 — Partial: review blocking policy (MEDIUM)
    elif result.robots.classification == "partial":
        agents = ", ".join(result.robots.blocked_agents)
        recs.append(
            Recommendation(
                message=(
                    f"robots.txt blocks some AI crawlers ({agents}). "
                    f"Review the blocking policy."
                ),
                severity=Severity.MEDIUM,
                category=cat,
            )
        )

    # FR-9.9 — No Sitemap directive in robots.txt (LOW)
    if result.robots.present and not result.robots.has_sitemap:
        recs.append(
            Recommendation(
                message="Add a Sitemap: directive to robots.txt.",
                severity=Severity.LOW,
                category=cat,
            )
        )

    # FR-9.4 — No llms.txt: recommend creating one (MEDIUM)
    if not result.llms_txt.present:
        recs.append(
            Recommendation(
                message=(
                    "Create a /llms.txt file with at minimum an H1 heading "
                    "and a summary blockquote."
                ),
                severity=Severity.MEDIUM,
                category=cat,
            )
        )
    else:
        # FR-9.5 — llms.txt lacks substantive summary (LOW)
        if not result.llms_txt.summary_substantive:
            recs.append(
                Recommendation(
                    message=(
                        "Add a substantive blockquote summary (>5 words) "
                        "to llms.txt."
                    ),
                    severity=Severity.LOW,
                    category=cat,
                )
            )

        # FR-9.6 — No resource links (MEDIUM)
        if result.llms_txt.resource_link_count == 0:
            recs.append(
                Recommendation(
                    message=(
                        "Add H2 sections with links to key resources "
                        "in llms.txt."
                    ),
                    severity=Severity.MEDIUM,
                    category=cat,
                )
            )

        # FR-9.7 — Resource links don't point to .md files (LOW)
        if (
            result.llms_txt.resource_link_count > 0
            and not result.llms_txt.has_md_links
        ):
            recs.append(
                Recommendation(
                    message=(
                        "Provide .md versions of linked resources for "
                        "better LLM consumption."
                    ),
                    severity=Severity.LOW,
                    category=cat,
                )
            )

        # FR-9.8 — No llms-full.txt (LOW)
        if not result.llms_full_txt.present:
            recs.append(
                Recommendation(
                    message=(
                        "Generate an llms-full.txt with all resource "
                        "content inlined."
                    ),
                    severity=Severity.LOW,
                    category=cat,
                )
            )

    # SPEC-ai-metadata FR-7.1 — No ai.txt (LOW)
    if not result.ai_metadata.ai_txt.present:
        recs.append(
            Recommendation(
                message="Create a /ai.txt file declaring AI interaction policies.",
                severity=Severity.LOW,
                category=cat,
            )
        )

    # SPEC-ai-metadata FR-7.2 — No ai-plugin.json or agent.json (LOW)
    plugin = result.ai_metadata.ai_plugin_json
    agent = result.ai_metadata.agent_json
    if not plugin.present and not agent.present:
        recs.append(
            Recommendation(
                message=(
                    "Create a /.well-known/ai-plugin.json manifest "
                    "to enable AI assistant discovery."
                ),
                severity=Severity.LOW,
                category=cat,
            )
        )

    # SPEC-ai-metadata FR-7.3 — ai-plugin.json present but invalid (LOW)
    if plugin.present and not plugin.valid:
        from botaudit.llm_discoverability import AI_PLUGIN_REQUIRED_FIELDS

        recs.append(
            Recommendation(
                message=(
                    "ai-plugin.json is missing required fields. "
                    f"Ensure these are present and non-empty: "
                    f"{', '.join(AI_PLUGIN_REQUIRED_FIELDS)}."
                ),
                severity=Severity.LOW,
                category=cat,
            )
        )

    return recs


# ---------------------------------------------------------------------------
# Type-aware recommendations (SPEC-page-type-heuristics FR-4)
# ---------------------------------------------------------------------------

# FR-4.6: Constant data structure for type-aware recommendation triggers.
# Each entry: (category_name, trigger_fn, message, severity)
# trigger_fn receives AnalysisResult and returns bool.

_ARTICLE_SCHEMA_TYPES = {"Article", "NewsArticle", "BlogPosting"}


def _type_recommend_article(
    analysis: AnalysisResult,
) -> list[Recommendation]:
    """FR-4.3 — Type-aware recommendations for article pages."""
    recs: list[Recommendation] = []
    sd = analysis.structured_data

    jsonld_types = {
        b.type_value for b in sd.json_ld_blocks if b.raw_valid and b.type_value
    }
    has_article_schema = bool(jsonld_types & _ARTICLE_SCHEMA_TYPES)

    if not has_article_schema:
        recs.append(Recommendation(
            message=(
                "[article] Add Article schema with headline, author, and "
                "datePublished for AI citation and search features"
            ),
            severity=Severity.HIGH,
            category="Structured Data",
        ))
    else:
        for block in sd.json_ld_blocks:
            if block.type_value not in _ARTICLE_SCHEMA_TYPES:
                continue
            if "datePublished" in block.properties_missing:
                recs.append(Recommendation(
                    message=(
                        "[article] Add datePublished to Article schema — AI "
                        "systems use publication date for recency and "
                        "relevance ranking"
                    ),
                    severity=Severity.MEDIUM,
                    category="Structured Data",
                ))
            if "author" in block.properties_missing:
                recs.append(Recommendation(
                    message=(
                        "[article] Add author to Article schema — AI "
                        "assistants use authorship for source attribution"
                    ),
                    severity=Severity.MEDIUM,
                    category="Structured Data",
                ))
            break  # only check first article-type block

    if "article" not in analysis.semantic_html.semantic_breakdown:
        recs.append(Recommendation(
            message=(
                "[article] Wrap the main content in an <article> element to "
                "help AI parsers identify the primary content"
            ),
            severity=Severity.MEDIUM,
            category="Semantic HTML",
        ))

    if "og:type" in sd.og_required_missing:
        recs.append(Recommendation(
            message=(
                "[article] Set og:type to article for consistent page-type "
                "signaling across AI and social platforms"
            ),
            severity=Severity.LOW,
            category="Structured Data",
        ))

    return recs


def _type_recommend_product(
    analysis: AnalysisResult,
) -> list[Recommendation]:
    """FR-4.3 — Type-aware recommendations for product pages."""
    recs: list[Recommendation] = []
    sd = analysis.structured_data

    jsonld_types = {
        b.type_value for b in sd.json_ld_blocks if b.raw_valid and b.type_value
    }
    has_product = "Product" in jsonld_types

    if not has_product:
        recs.append(Recommendation(
            message=(
                "[product] Add Product schema with name, description, and "
                "pricing for AI shopping assistants and rich search results"
            ),
            severity=Severity.HIGH,
            category="Structured Data",
        ))
    else:
        for block in sd.json_ld_blocks:
            if block.type_value != "Product":
                continue
            if "description" in block.properties_missing:
                recs.append(Recommendation(
                    message=(
                        "[product] Add description to Product schema — AI "
                        "comparison tools rely on structured product "
                        "descriptions"
                    ),
                    severity=Severity.MEDIUM,
                    category="Structured Data",
                ))
            break

        has_offer_with_price = any(
            b.type_value == "Offer" and "price" not in b.properties_missing
            for b in sd.json_ld_blocks
            if b.raw_valid
        )
        if not has_offer_with_price:
            recs.append(Recommendation(
                message=(
                    "[product] Add an Offer with price and priceCurrency to "
                    "Product schema for AI price comparison"
                ),
                severity=Severity.MEDIUM,
                category="Structured Data",
            ))

    if not sd.has_meta_description or sd.meta_description_length_class == "too_short":
        recs.append(Recommendation(
            message=(
                "[product] Add a descriptive meta description summarizing "
                "the product — AI assistants use this as a product summary"
            ),
            severity=Severity.MEDIUM,
            category="Structured Data",
        ))

    return recs


def _type_recommend_documentation(
    analysis: AnalysisResult,
) -> list[Recommendation]:
    """FR-4.3 — Type-aware recommendations for documentation pages."""
    recs: list[Recommendation] = []

    if analysis.content_availability.word_count < 200:
        recs.append(Recommendation(
            message=(
                "[documentation] Documentation pages should render "
                "substantive content server-side — AI systems cannot "
                "execute JavaScript to reveal hidden content"
            ),
            severity=Severity.HIGH,
            category="Content Availability",
        ))

    ld = analysis.link_discoverability
    if ld.total_links > 0 and ld.navigable_ratio < 0.8:
        recs.append(Recommendation(
            message=(
                "[documentation] Documentation pages depend on strong "
                "navigation — ensure all links use real URLs, not "
                "JavaScript handlers"
            ),
            severity=Severity.MEDIUM,
            category="Link Discoverability",
        ))

    if "nav" not in analysis.semantic_html.semantic_breakdown:
        recs.append(Recommendation(
            message=(
                "[documentation] Add a <nav> element for documentation "
                "navigation — AI crawlers use it to discover related pages"
            ),
            severity=Severity.MEDIUM,
            category="Semantic HTML",
        ))

    jsonld_types = {
        b.type_value for b in analysis.structured_data.json_ld_blocks
        if b.raw_valid and b.type_value
    }
    if "HowTo" not in jsonld_types and "Course" not in jsonld_types:
        recs.append(Recommendation(
            message=(
                "[documentation] Consider adding HowTo schema for "
                "tutorial/guide content to enable AI step-by-step "
                "presentation"
            ),
            severity=Severity.LOW,
            category="Structured Data",
        ))

    return recs


def _type_recommend_homepage(
    analysis: AnalysisResult,
) -> list[Recommendation]:
    """FR-4.3 — Type-aware recommendations for homepage pages."""
    recs: list[Recommendation] = []

    jsonld_types = {
        b.type_value for b in analysis.structured_data.json_ld_blocks
        if b.raw_valid and b.type_value
    }
    if "WebSite" not in jsonld_types and "Organization" not in jsonld_types:
        recs.append(Recommendation(
            message=(
                "[homepage] Add WebSite or Organization schema to the "
                "homepage — AI systems use this to understand site identity "
                "and purpose"
            ),
            severity=Severity.MEDIUM,
            category="Structured Data",
        ))

    if not analysis.metadata.has_canonical:
        recs.append(Recommendation(
            message=(
                "[homepage] Homepages should have a canonical URL to prevent "
                "AI systems from indexing duplicate versions"
            ),
            severity=Severity.MEDIUM,
            category="Metadata & Discoverability",
        ))

    if not analysis.metadata.has_sitemap_ref:
        recs.append(Recommendation(
            message=(
                "[homepage] Add a <link rel=\"sitemap\"> to the homepage — "
                "AI crawlers use it as the primary entry point for site "
                "discovery"
            ),
            severity=Severity.MEDIUM,
            category="Metadata & Discoverability",
        ))

    return recs


def _type_recommend_listing(
    analysis: AnalysisResult,
) -> list[Recommendation]:
    """FR-4.3 — Type-aware recommendations for listing pages."""
    recs: list[Recommendation] = []

    jsonld_types = {
        b.type_value for b in analysis.structured_data.json_ld_blocks
        if b.raw_valid and b.type_value
    }
    if "ItemList" not in jsonld_types and "CollectionPage" not in jsonld_types:
        recs.append(Recommendation(
            message=(
                "[listing] Add ItemList schema to listing pages — AI "
                "systems use it to understand page structure and item "
                "relationships"
            ),
            severity=Severity.MEDIUM,
            category="Structured Data",
        ))

    ld = analysis.link_discoverability
    if ld.total_links > 0 and ld.navigable_ratio < 0.7:
        recs.append(Recommendation(
            message=(
                "[listing] Listing pages are navigation-heavy — ensure "
                "category and item links use real URLs for AI "
                "discoverability"
            ),
            severity=Severity.MEDIUM,
            category="Link Discoverability",
        ))

    return recs


# Dispatch: page_type → recommender.
_TYPE_RECOMMENDERS: dict[str, object] = {
    "article": _type_recommend_article,
    "product": _type_recommend_product,
    "documentation": _type_recommend_documentation,
    "homepage": _type_recommend_homepage,
    "listing": _type_recommend_listing,
}


def _get_type_aware_recommendations(
    analysis: AnalysisResult,
    category_name: str,
    page_type: str,
) -> list[Recommendation]:
    """Return type-aware recommendations for *category_name* given *page_type*.

    FR-4.2: Only returns recs whose ``category`` matches *category_name*.
    """
    recommender = _TYPE_RECOMMENDERS.get(page_type)
    if recommender is None:
        return []
    all_recs = recommender(analysis)
    return [r for r in all_recs if r.category == category_name]


# --- Recommender dispatch table (§7.5.2) ---

_RECOMMENDERS = {
    "Semantic HTML": lambda analysis: recommend_semantic_html(analysis.semantic_html),
    "Content Availability": lambda analysis: recommend_content_availability(
        analysis.content_availability
    ),
    "Link Discoverability": lambda analysis: recommend_link_discoverability(
        analysis.link_discoverability
    ),
    "Structured Data": lambda analysis: recommend_structured_data(
        analysis.structured_data
    ),
    "Metadata & Discoverability": lambda analysis: recommend_metadata(
        analysis.metadata
    ),
    "LLM Discoverability": lambda analysis: (
        recommend_llm_discovery(analysis.llm_discovery)
        if analysis.llm_discovery is not None
        else []
    ),
}

# §7.3.1 — Severity ordering
_SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


def recommend(
    analysis: AnalysisResult,
    categories: list[CategoryResult],
    *,
    page_type: PageTypeResult | None = None,
) -> list[CategoryResult]:
    """§7.1 — Return new CategoryResults with recommendations attached.

    Categories scoring below threshold receive recommendations sorted
    by severity (§7.3.1).  Categories at or above threshold are returned
    unchanged.

    SPEC-page-type-heuristics FR-4: When *page_type* is provided and
    non-generic, type-aware recommendations are appended.
    """
    pt_name = (
        page_type.page_type
        if page_type is not None and page_type.page_type != "generic"
        else None
    )

    result: list[CategoryResult] = []
    for cat in categories:
        # §7.1.2 — Skip categories scoring 90+
        if cat.score >= RECOMMENDATION_THRESHOLD:
            result.append(cat)
            continue

        recommender = _RECOMMENDERS.get(cat.name)
        recs = recommender(analysis) if recommender is not None else []

        # FR-4.1 / FR-4.4: Append type-aware recs for this category.
        if pt_name is not None:
            recs.extend(
                _get_type_aware_recommendations(analysis, cat.name, pt_name)
            )

        # §7.3.1 — Sort by severity
        recs.sort(key=lambda r: _SEVERITY_ORDER.get(r.severity, 99))
        result.append(
            CategoryResult(
                name=cat.name,
                score=cat.score,
                findings=cat.findings,
                recommendations=recs,
            )
        )
    return result
