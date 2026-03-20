"""Tests for LLM Discoverability module (SPEC-llms-txt.md)."""

import unittest

from botaudit.grading import score_llm_discovery
from botaudit.llm_discoverability import (
    LLMDiscoverabilityResult,
    LlmsFullTxtResult,
    LlmsTxtResult,
    analyze_llm_discovery,
    analyze_llms_full_txt,
    analyze_llms_txt,
)
from botaudit.models import Severity
from botaudit.recommendations import recommend_llm_discovery
from botaudit.robots_analysis import RobotsTxtResult


# ── FR-3: llms.txt structural validation ──────────────────────────────


class TestAnalyzeLlmsTxt(unittest.TestCase):
    """FR-3 — llms.txt structural validation."""

    # FR-3.2 — H1 heading

    def test_none_content_returns_not_present(self):
        result = analyze_llms_txt(None)
        self.assertFalse(result.present)
        self.assertFalse(result.is_valid)

    def test_empty_content_returns_not_present(self):
        result = analyze_llms_txt("")
        self.assertFalse(result.present)

    def test_whitespace_only_returns_not_present(self):
        result = analyze_llms_txt("   \n\n  ")
        self.assertFalse(result.present)

    def test_valid_h1(self):
        result = analyze_llms_txt("# My Project\n")
        self.assertTrue(result.present)
        self.assertTrue(result.has_h1)
        self.assertEqual(result.h1_text, "My Project")
        self.assertTrue(result.is_valid)

    def test_h1_not_first_line_is_invalid(self):
        result = analyze_llms_txt("Some text\n# My Project\n")
        self.assertTrue(result.present)
        self.assertFalse(result.has_h1)
        self.assertFalse(result.is_valid)

    def test_multiple_h1_is_invalid(self):
        result = analyze_llms_txt("# First\n# Second\n")
        self.assertTrue(result.present)
        self.assertFalse(result.has_h1)
        self.assertFalse(result.is_valid)

    # FR-3.3 — Blockquote summary

    def test_blockquote_after_h1(self):
        content = "# Project\n\n> A short summary of the project\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.has_blockquote)
        self.assertEqual(result.blockquote_text, "A short summary of the project")

    def test_multiline_blockquote(self):
        content = "# Project\n> Line one\n> Line two\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.has_blockquote)
        self.assertEqual(result.blockquote_text, "Line one Line two")

    def test_no_blockquote(self):
        content = "# Project\n\n## Section\n"
        result = analyze_llms_txt(content)
        self.assertFalse(result.has_blockquote)

    def test_blockquote_after_h2_not_counted(self):
        content = "# Project\n## Section\n> This is not a summary\n"
        result = analyze_llms_txt(content)
        self.assertFalse(result.has_blockquote)

    # FR-3.4 — H2 sections and resource links

    def test_h2_sections_counted(self):
        content = "# Project\n## Docs\n## API\n## Guides\n"
        result = analyze_llms_txt(content)
        self.assertEqual(result.h2_count, 3)
        self.assertEqual(result.h2_sections, ["Docs", "API", "Guides"])

    def test_resource_links_in_list_items(self):
        content = (
            "# Project\n"
            "## Docs\n"
            "- [API](https://example.com/api)\n"
            "- [Guide](https://example.com/guide)\n"
        )
        result = analyze_llms_txt(content)
        self.assertEqual(result.resource_link_count, 2)
        self.assertEqual(len(result.resource_links), 2)

    def test_links_outside_h2_not_counted(self):
        content = "# Project\n- [Link](https://example.com)\n## Section\n"
        result = analyze_llms_txt(content)
        self.assertEqual(result.resource_link_count, 0)

    def test_links_not_in_list_items_not_counted(self):
        content = "# Project\n## Docs\n[Link](https://example.com)\n"
        result = analyze_llms_txt(content)
        self.assertEqual(result.resource_link_count, 0)

    # FR-3.5 — Optional section

    def test_optional_section_detected(self):
        content = "# Project\n## Docs\n## Optional\n- [Extra](extra.md)\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.has_optional_section)

    def test_optional_section_case_insensitive(self):
        content = "# Project\n## optional\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.has_optional_section)

    def test_no_optional_section(self):
        content = "# Project\n## Docs\n"
        result = analyze_llms_txt(content)
        self.assertFalse(result.has_optional_section)


# ── FR-4: llms.txt content quality ────────────────────────────────────


class TestLlmsTxtQuality(unittest.TestCase):
    """FR-4 — llms.txt content quality assessment."""

    # FR-4.1 — Summary substantiveness

    def test_substantive_summary(self):
        content = "# Project\n> This is a comprehensive summary of the project for LLMs\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.summary_substantive)

    def test_short_summary_not_substantive(self):
        content = "# Project\n> Short summary\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.has_blockquote)
        self.assertFalse(result.summary_substantive)

    def test_exactly_five_words_not_substantive(self):
        content = "# Project\n> One two three four five\n"
        result = analyze_llms_txt(content)
        self.assertFalse(result.summary_substantive)

    def test_six_words_is_substantive(self):
        content = "# Project\n> One two three four five six\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.summary_substantive)

    # FR-4.4 — Markdown resource detection

    def test_md_links_detected(self):
        content = "# Project\n## Docs\n- [API](docs/api.md)\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.has_md_links)

    def test_non_md_links(self):
        content = "# Project\n## Docs\n- [API](https://example.com/api)\n"
        result = analyze_llms_txt(content)
        self.assertFalse(result.has_md_links)

    def test_md_extension_case_insensitive(self):
        content = "# Project\n## Docs\n- [API](docs/api.MD)\n"
        result = analyze_llms_txt(content)
        self.assertTrue(result.has_md_links)


# ── FR-5: llms-full.txt detection ─────────────────────────────────────


class TestAnalyzeLlmsFullTxt(unittest.TestCase):
    """FR-5 — llms-full.txt detection."""

    def test_none_not_present(self):
        result = analyze_llms_full_txt(None)
        self.assertFalse(result.present)

    def test_empty_not_present(self):
        result = analyze_llms_full_txt("")
        self.assertFalse(result.present)

    def test_whitespace_only_not_present(self):
        result = analyze_llms_full_txt("   \n\n  ")
        self.assertFalse(result.present)

    def test_valid_content_present(self):
        result = analyze_llms_full_txt("# Full content here\nSome text.")
        self.assertTrue(result.present)


# ── FR-6: Scoring ─────────────────────────────────────────────────────


class TestScoreLlmDiscovery(unittest.TestCase):
    """FR-6 — LLM Discoverability scoring."""

    def _make_result(self, robots=None, llms=None, llms_full=None):
        return LLMDiscoverabilityResult(
            robots=robots or RobotsTxtResult(classification="open"),
            llms_txt=llms or LlmsTxtResult(),
            llms_full_txt=llms_full or LlmsFullTxtResult(),
        )

    # FR-6.6 — Baseline: no files = 30
    def test_no_files_scores_30(self):
        result = analyze_llm_discovery(None, None, None)
        cat = score_llm_discovery(result)
        self.assertEqual(cat.score, 30.0)

    # FR-6.2 — AI crawlers not blocked (30 pts)
    def test_open_robots_gets_30(self):
        result = self._make_result(
            robots=RobotsTxtResult(present=True, classification="open"),
        )
        cat = score_llm_discovery(result)
        self.assertGreaterEqual(cat.score, 30)

    def test_partial_robots_gets_30(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="partial",
                blocked_agents=["GPTBot"],
            ),
        )
        cat = score_llm_discovery(result)
        self.assertGreaterEqual(cat.score, 30)

    # FR-6.3 — Restrictive: AI crawlers + botaudit score 0
    def test_restrictive_no_crawler_points(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="restrictive",
                blocked_agents=[f"bot{i}" for i in range(9)],
                tool_allowed=False,
            ),
        )
        cat = score_llm_discovery(result)
        # No 30 pts for crawlers, no 5 pts for botaudit
        self.assertEqual(cat.score, 0)

    def test_restrictive_cap_at_65(self):
        """FR-6.3 — Max score with restrictive is <=65."""
        llms = LlmsTxtResult(
            present=True,
            is_valid=True,
            has_h1=True,
            h1_text="Project",
            has_blockquote=True,
            blockquote_text="A substantive summary with more than five words",
            summary_substantive=True,
            h2_count=2,
            resource_link_count=3,
            has_md_links=True,
        )
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="restrictive",
                blocked_agents=[f"bot{i}" for i in range(9)],
                has_sitemap=True,
                tool_allowed=False,
            ),
            llms=llms,
            llms_full=LlmsFullTxtResult(present=True),
        )
        cat = score_llm_discovery(result)
        self.assertLessEqual(cat.score, 65)

    # FR-6.2 — Explicit Allow (5 pts)
    def test_explicit_allow_bonus(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="open",
                agent_statuses={"ClaudeBot": "allowed"},
            ),
        )
        cat = score_llm_discovery(result)
        # 30 (not blocked) + 5 (explicit allow) + 5 (tool allowed)
        self.assertEqual(cat.score, 40)

    # FR-6.2 — Sitemap (5 pts)
    def test_sitemap_bonus(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="open",
                has_sitemap=True,
            ),
        )
        cat = score_llm_discovery(result)
        # 30 + 5 (sitemap) + 5 (tool allowed)
        self.assertEqual(cat.score, 40)

    # FR-6.2 — llms.txt signals
    def test_llms_txt_all_signals(self):
        llms = LlmsTxtResult(
            present=True,
            is_valid=True,
            has_h1=True,
            h1_text="Project",
            has_blockquote=True,
            blockquote_text="A substantive summary with more than five words",
            summary_substantive=True,
            h2_count=2,
            resource_link_count=5,
            has_md_links=True,
        )
        result = self._make_result(
            robots=RobotsTxtResult(present=True, classification="open"),
            llms=llms,
            llms_full=LlmsFullTxtResult(present=True),
        )
        cat = score_llm_discovery(result)
        # 30 + 20 + 5 + 5 + 10 + 5 + 10 + 5 = 90
        self.assertEqual(cat.score, 90)

    # FR-6.4 — No llms.txt sub-signals without llms.txt
    def test_no_llms_txt_no_subsignals(self):
        result = self._make_result(
            robots=RobotsTxtResult(present=True, classification="open"),
            llms=LlmsTxtResult(present=False),
            llms_full=LlmsFullTxtResult(present=True),
        )
        cat = score_llm_discovery(result)
        # 30 (not blocked) + 5 (tool) = 35 — no llms.txt or llms-full credit
        self.assertEqual(cat.score, 35)

    # FR-5.4 / FR-6.5 — llms-full.txt only credited with llms.txt
    def test_llms_full_without_llms_no_credit(self):
        result = self._make_result(
            llms=LlmsTxtResult(present=False),
            llms_full=LlmsFullTxtResult(present=True),
        )
        cat1 = score_llm_discovery(result)

        result_no_full = self._make_result(
            llms=LlmsTxtResult(present=False),
            llms_full=LlmsFullTxtResult(present=False),
        )
        cat2 = score_llm_discovery(result_no_full)

        self.assertEqual(cat1.score, cat2.score)

    # FR-6.2 — botaudit not blocked (5 pts)
    def test_tool_allowed_when_present(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="open",
                tool_allowed=True,
            ),
        )
        cat = score_llm_discovery(result)
        self.assertEqual(cat.score, 35)  # 30 + 5

    def test_tool_not_awarded_without_robots(self):
        """botaudit signal only awarded when robots.txt is present."""
        result = self._make_result(
            robots=RobotsTxtResult(present=False, classification="open"),
        )
        cat = score_llm_discovery(result)
        self.assertEqual(cat.score, 30)  # Just the "not blocked" baseline

    def test_category_name(self):
        result = self._make_result()
        cat = score_llm_discovery(result)
        self.assertEqual(cat.name, "LLM Discoverability")


# ── FR-9: Recommendations ────────────────────────────────────────────


class TestRecommendLlmDiscovery(unittest.TestCase):
    """FR-9 — LLM Discoverability recommendations."""

    def _make_result(self, robots=None, llms=None, llms_full=None):
        return LLMDiscoverabilityResult(
            robots=robots or RobotsTxtResult(classification="open"),
            llms_txt=llms or LlmsTxtResult(),
            llms_full_txt=llms_full or LlmsFullTxtResult(),
        )

    # FR-9.2 — Restrictive → HIGH
    def test_restrictive_high_rec(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="restrictive",
                blocked_agents=["GPTBot", "ClaudeBot"],
            ),
        )
        recs = recommend_llm_discovery(result)
        high_recs = [r for r in recs if r.severity == Severity.HIGH]
        self.assertEqual(len(high_recs), 1)
        self.assertIn("GPTBot", high_recs[0].message)
        self.assertIn("ClaudeBot", high_recs[0].message)

    # FR-9.3 — Partial → MEDIUM
    def test_partial_medium_rec(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="partial",
                blocked_agents=["GPTBot"],
            ),
        )
        recs = recommend_llm_discovery(result)
        medium_recs = [r for r in recs if r.severity == Severity.MEDIUM]
        self.assertTrue(any("GPTBot" in r.message for r in medium_recs))

    # FR-9.4 — No llms.txt → MEDIUM
    def test_no_llms_txt_rec(self):
        result = self._make_result(llms=LlmsTxtResult(present=False))
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.MEDIUM and "llms.txt" in r.message
            for r in recs
        ))

    # FR-9.5 — No summary → LOW
    def test_no_summary_rec(self):
        result = self._make_result(
            llms=LlmsTxtResult(present=True, summary_substantive=False),
        )
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.LOW and "summary" in r.message.lower()
            for r in recs
        ))

    # FR-9.6 — No resource links → MEDIUM
    def test_no_resource_links_rec(self):
        result = self._make_result(
            llms=LlmsTxtResult(present=True, resource_link_count=0),
        )
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.MEDIUM and "links" in r.message.lower()
            for r in recs
        ))

    # FR-9.7 — No .md links → LOW
    def test_no_md_links_rec(self):
        result = self._make_result(
            llms=LlmsTxtResult(
                present=True,
                resource_link_count=3,
                has_md_links=False,
            ),
        )
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.LOW and ".md" in r.message
            for r in recs
        ))

    # FR-9.8 — No llms-full.txt → LOW
    def test_no_llms_full_rec(self):
        result = self._make_result(
            llms=LlmsTxtResult(present=True),
            llms_full=LlmsFullTxtResult(present=False),
        )
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.LOW and "llms-full" in r.message.lower()
            for r in recs
        ))

    # FR-9.9 — No Sitemap → LOW
    def test_no_sitemap_rec(self):
        result = self._make_result(
            robots=RobotsTxtResult(present=True, has_sitemap=False),
        )
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.LOW and "sitemap" in r.message.lower()
            for r in recs
        ))

    def test_no_sitemap_rec_only_when_robots_present(self):
        result = self._make_result(
            robots=RobotsTxtResult(present=False),
        )
        recs = recommend_llm_discovery(result)
        self.assertFalse(any("sitemap" in r.message.lower() for r in recs))

    # Open site with full llms.txt — minimal recs
    def test_well_configured_site_few_recs(self):
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True,
                classification="open",
                has_sitemap=True,
            ),
            llms=LlmsTxtResult(
                present=True,
                summary_substantive=True,
                resource_link_count=5,
                has_md_links=True,
            ),
            llms_full=LlmsFullTxtResult(present=True),
        )
        recs = recommend_llm_discovery(result)
        self.assertEqual(len(recs), 0)
