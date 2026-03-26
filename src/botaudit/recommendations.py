"""Section 7 — Recommendation engine for AI accessibility improvements.

7.1  Generate actionable recommendations per category when score < 90.
7.3  Order by severity (high → medium → low).
7.4  Per-category recommendation rules.
7.5  One pure function per category, extensible without modifying core logic.
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
    analysis: AnalysisResult, categories: list[CategoryResult]
) -> list[CategoryResult]:
    """§7.1 — Return new CategoryResults with recommendations attached.

    Categories scoring below threshold receive recommendations sorted
    by severity (§7.3.1).  Categories at or above threshold are returned
    unchanged.
    """
    result: list[CategoryResult] = []
    for cat in categories:
        # §7.1.2 — Skip categories scoring 90+
        if cat.score >= RECOMMENDATION_THRESHOLD:
            result.append(cat)
            continue

        recommender = _RECOMMENDERS.get(cat.name)
        if recommender is None:
            result.append(cat)
            continue

        recs = recommender(analysis)
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
