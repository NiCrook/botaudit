"""Section 4 — Grading of analysis results for AI accessibility.

4.1  Assign a score (0–100) to each analysis category.
4.2  Compute an overall weighted score from the category scores.
4.3  Map the overall score to a letter grade (A–F).
4.4  Weight categories by relative importance to AI accessibility.
"""

from __future__ import annotations

from botaudit.analysis import (
    AnalysisResult,
    ContentAvailabilityResult,
    LinkDiscoverabilityResult,
    MetadataResult,
    SemanticHTMLResult,
    StructuredDataResult,
)
from botaudit.llm_discoverability import LLMDiscoverabilityResult
from botaudit.models import CategoryResult, Report


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


# --- Per-category scoring (§4.1) ---


def score_semantic_html(result: SemanticHTMLResult) -> CategoryResult:
    """Score Semantic HTML (§3.1).

    Based on the ratio of semantic to total container elements.
    Documents with no container elements are not penalized (§3.1.4).
    """
    findings: list[str] = []
    total = result.semantic_count + result.generic_count

    if total == 0:
        score = 100.0
        findings.append("No container elements found — not penalized.")
    else:
        score = _clamp(result.semantic_ratio * 100)
        findings.append(
            f"{result.semantic_count} semantic vs "
            f"{result.generic_count} generic elements "
            f"(ratio: {result.semantic_ratio:.0%})"
        )

    if result.semantic_breakdown:
        tags = ", ".join(
            f"{tag} ({n})"
            for tag, n in sorted(
                result.semantic_breakdown.items(), key=lambda x: -x[1]
            )
        )
        findings.append(f"Semantic tags: {tags}")

    return CategoryResult(name="Semantic HTML", score=round(score, 1), findings=findings)


def score_content_availability(result: ContentAvailabilityResult) -> CategoryResult:
    """Score Content Availability (§3.2).

    Heavily weighted toward having meaningful visible text.
    Bonus for <noscript> fallback content.
    """
    findings: list[str] = []
    score = 0.0

    if not result.has_meaningful_content:
        findings.append("Page appears to be an empty shell (<=10 words of text).")
        if result.has_noscript:
            score = 20.0
            findings.append("<noscript> fallback present — partial credit.")
        return CategoryResult(
            name="Content Availability", score=score, findings=findings
        )

    # Meaningful content: base 60 + up to 30 for word count + 10 for noscript
    score = 60.0
    findings.append(f"{result.word_count} words of visible text.")

    # Scale word-count bonus: 100+ words earns full 30 points
    word_bonus = _clamp(result.word_count / 100 * 30, hi=30.0)
    score += word_bonus

    if result.has_noscript:
        score += 10.0
        findings.append("<noscript> fallback present.")

    return CategoryResult(
        name="Content Availability", score=_clamp(round(score, 1)), findings=findings
    )


def score_link_discoverability(result: LinkDiscoverabilityResult) -> CategoryResult:
    """Score Link Discoverability (§3.3).

    Based on navigable link ratio and presence of links.
    """
    findings: list[str] = []

    if result.total_links == 0:
        findings.append("No links found.")
        return CategoryResult(
            name="Link Discoverability", score=0.0, findings=findings
        )

    score = _clamp(result.navigable_ratio * 100)
    findings.append(
        f"{result.navigable_links} navigable / "
        f"{result.total_links} total links "
        f"(ratio: {result.navigable_ratio:.0%})"
    )
    if result.non_navigable_links:
        findings.append(
            f"{result.non_navigable_links} non-navigable links "
            f'(href="#", javascript:, or empty).'
        )

    return CategoryResult(
        name="Link Discoverability",
        score=round(score, 1),
        findings=findings,
    )


def score_structured_data(result: StructuredDataResult) -> CategoryResult:
    """Score Structured Data (§3.4).

    Points awarded for each format present:
    JSON-LD (40), Open Graph (30), meta description (30).
    """
    findings: list[str] = []
    score = 0.0

    if result.has_json_ld:
        score += 40.0
        findings.append(f"JSON-LD present ({result.json_ld_count} block(s)).")
    else:
        findings.append("No JSON-LD found.")

    if result.has_open_graph:
        score += 30.0
        findings.append(f"Open Graph tags present ({len(result.open_graph_tags)}).")
    else:
        findings.append("No Open Graph tags found.")

    if result.has_meta_description:
        score += 30.0
        findings.append("Meta description present.")
    else:
        findings.append("No meta description found.")

    return CategoryResult(
        name="Structured Data", score=round(score, 1), findings=findings
    )


def score_metadata(result: MetadataResult) -> CategoryResult:
    """Score Metadata & Discoverability (§3.5).

    Points: title (40), canonical (25), robots meta (20), sitemap ref (15).
    """
    findings: list[str] = []
    score = 0.0

    if result.has_title:
        score += 40.0
        findings.append(f"Title: \"{result.title}\"")
    else:
        findings.append("No <title> element found.")

    if result.has_canonical:
        score += 25.0
        findings.append(f"Canonical URL: {result.canonical_url}")
    else:
        findings.append("No canonical URL.")

    if result.has_robots_meta:
        score += 20.0
        findings.append(f"Robots: {result.robots_directives}")
    else:
        findings.append("No robots meta tag.")

    if result.has_sitemap_ref:
        score += 15.0
        findings.append("Sitemap reference found.")
    else:
        findings.append("No sitemap reference in HTML.")

    return CategoryResult(
        name="Metadata & Discoverability",
        score=round(score, 1),
        findings=findings,
    )


def score_llm_discovery(result: LLMDiscoverabilityResult) -> CategoryResult:
    """FR-6 / SPEC-ai-metadata FR-5 — Score the LLM Discoverability category (0–100).

    Revised scoring breakdown (SPEC-ai-metadata FR-5.2):
      AI crawlers not blocked          30 pts
      Explicit Allow for AI bots        5 pts
      Sitemap in robots.txt             5 pts
      llms.txt present                 15 pts  (was 20)
      llms.txt valid structure          5 pts
      llms.txt summary present          5 pts
      llms.txt resource links           5 pts  (was 10)
      llms.txt markdown resources       5 pts
      llms-full.txt present             5 pts  (was 10)
      botaudit not blocked              5 pts
      ai.txt present                    5 pts  NEW (SPEC-ai-metadata)
      AI metadata manifest present      5 pts  NEW (SPEC-ai-metadata)
      AI metadata manifest valid        5 pts  NEW (SPEC-ai-metadata)
                                     --------
                                      100 pts

    FR-6.3 / SPEC-ai-metadata FR-5.8: When restrictive, AI crawlers (30) and
        botaudit (5) score 0 — max 65.
    FR-6.4: No llms.txt sub-signals without llms.txt present.
    FR-6.5: No llms-full.txt credit without llms.txt present.
    SPEC-ai-metadata FR-5.7: ai.txt/manifest signals independent of llms.txt.
    SPEC-ai-metadata FR-5.9: No robots.txt + no discovery files = 30 (baseline).
    """
    findings: list[str] = []
    score = 0.0

    robots = result.robots
    llms = result.llms_txt
    llms_full = result.llms_full_txt
    ai_meta = result.ai_metadata

    # --- Signal 1: AI crawlers not blocked (30 pts) ---
    # FR-6.3 / SPEC-ai-metadata FR-5.8: Scores 0 when restrictive
    if robots.classification in ("open", "partial"):
        score += 30
        if not robots.present:
            findings.append("No robots.txt found — AI crawlers not blocked.")
        elif robots.classification == "open":
            findings.append("robots.txt present — no AI crawlers blocked.")
        else:
            findings.append(
                f"robots.txt: {len(robots.blocked_agents)} AI crawler(s) blocked "
                f"({', '.join(robots.blocked_agents)})."
            )
    else:  # restrictive
        findings.append(
            f"robots.txt blocks all known AI crawlers: "
            f"{', '.join(robots.blocked_agents)}."
        )

    # --- Signal 2: Explicit Allow for AI bots (5 pts) ---
    allowed = [a for a, s in robots.agent_statuses.items() if s == "allowed"]
    if allowed:
        score += 5
        findings.append(f"Explicit Allow for: {', '.join(allowed)}.")

    # --- Signal 3: Sitemap in robots.txt (5 pts) ---
    if robots.has_sitemap:
        score += 5
        findings.append("Sitemap directive found in robots.txt.")

    # --- Signal 4: llms.txt present (15 pts) ---
    # SPEC-ai-metadata FR-5.2: reduced from 20 to 15
    if llms.present:
        score += 15
        if llms.h1_text:
            findings.append(f'llms.txt present (title: "{llms.h1_text}").')
        else:
            findings.append("llms.txt present.")

        # --- Signal 5: Valid structure (5 pts) ---
        if llms.is_valid:
            score += 5
            findings.append("llms.txt has valid structure (H1 heading).")

        # --- Signal 6: Summary present and substantive (5 pts) ---
        if llms.summary_substantive:
            score += 5
            findings.append("Substantive summary found in llms.txt.")
        elif llms.has_blockquote:
            findings.append("Summary present but not substantive (<=5 words).")

        # --- Signal 7: Resource links (5 pts) ---
        # SPEC-ai-metadata FR-5.2: reduced from 10 to 5
        if llms.resource_link_count > 0 and llms.h2_count > 0:
            score += 5
            findings.append(
                f"{llms.resource_link_count} resource link(s) across "
                f"{llms.h2_count} section(s)."
            )
        else:
            findings.append("No resource links found in llms.txt.")

        # --- Signal 8: Markdown resources (5 pts) ---
        if llms.has_md_links:
            score += 5
            findings.append("Resource links to .md files found.")

        # --- Signal 9: llms-full.txt present (5 pts) ---
        # SPEC-ai-metadata FR-5.2: reduced from 10 to 5
        # FR-5.4 / FR-6.5: Only scored when llms.txt is also present
        if llms_full.present:
            score += 5
            findings.append("llms-full.txt present.")
        else:
            findings.append("No llms-full.txt found.")
    else:
        findings.append("No llms.txt found.")
        # FR-6.4/6.5: No sub-signal credit without llms.txt

    # --- Signal 10: botaudit not blocked (5 pts) ---
    # FR-6.3 / SPEC-ai-metadata FR-5.8: Scores 0 when restrictive
    if robots.present and robots.classification != "restrictive" and robots.tool_allowed:
        score += 5
    elif robots.present and not robots.tool_allowed:
        findings.append("robots.txt blocks the botaudit user-agent.")

    # --- Signal 11: ai.txt present (5 pts) ---
    # SPEC-ai-metadata FR-5.7: independent of llms.txt
    if ai_meta.ai_txt.present:
        score += 5
        # FR-6.1
        findings.append(f"ai.txt present ({ai_meta.ai_txt.line_count} lines).")
    else:
        # FR-6.2
        findings.append("No ai.txt file found.")

    # --- Signal 12: AI metadata manifest present (5 pts) ---
    # SPEC-ai-metadata FR-5.3: at least one of ai-plugin.json or agent.json
    plugin = ai_meta.ai_plugin_json
    agent = ai_meta.agent_json
    manifest_present = plugin.present or agent.present
    if manifest_present:
        score += 5

    # FR-6.3 / FR-6.4 / FR-6.5 — ai-plugin.json findings
    if plugin.present and plugin.valid:
        findings.append(
            f'ai-plugin.json present — valid plugin manifest '
            f'(name: "{plugin.name_for_human}").'
        )
    elif plugin.present:
        findings.append("ai-plugin.json present but missing required fields.")
    else:
        findings.append("No ai-plugin.json found.")

    # FR-6.6 / FR-6.7 — agent.json findings
    if agent.present:
        findings.append("agent.json present.")
    else:
        findings.append("No agent.json found.")

    # --- Signal 13: AI metadata manifest valid (5 pts) ---
    # SPEC-ai-metadata FR-5.4: ai-plugin.json valid OR agent.json present (non-empty)
    manifest_valid = plugin.valid or agent.present
    if manifest_valid:
        score += 5

    return CategoryResult(
        name="LLM Discoverability",
        score=_clamp(round(score, 1)),
        findings=findings,
    )


# --- Overall grading (§4.2, §4.3, §4.4) ---


def grade(
    analysis: AnalysisResult,
    url: str,
    *,
    weights: dict[str, float] | None = None,
) -> Report:
    """Build a graded Report from analysis results.

    §4.1 — scores each category (0–100).
    §4.2 — computes a weighted overall score.
    §4.3 — maps the overall score to a letter grade.
    §4.4 — applies category weights defined in models.CATEGORY_WEIGHTS.

    SPEC-custom-weights: *weights* overrides default weights when provided.
    """
    categories = [
        score_content_availability(analysis.content_availability),
        score_semantic_html(analysis.semantic_html),
        score_link_discoverability(analysis.link_discoverability),
        score_structured_data(analysis.structured_data),
        score_metadata(analysis.metadata),
    ]

    # FR-7.1 — LLM Discoverability as sixth category
    if analysis.llm_discovery is not None:
        categories.append(score_llm_discovery(analysis.llm_discovery))

    report = Report(url=url, categories=categories)
    report.compute_grade(weights=weights)  # §4.2 + §4.3
    return report
