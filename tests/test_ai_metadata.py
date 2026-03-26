"""Tests for AI Metadata Detection (SPEC-ai-metadata.md)."""

import json
import unittest

from botaudit.grading import score_llm_discovery
from botaudit.llm_discoverability import (
    AI_PLUGIN_REQUIRED_FIELDS,
    AIMetadataResult,
    AgentJsonResult,
    AiPluginJsonResult,
    AiTxtResult,
    LLMDiscoverabilityResult,
    LlmsFullTxtResult,
    LlmsTxtResult,
    _is_json_content_type,
    _is_text_content_type,
    analyze_agent_json,
    analyze_ai_plugin_json,
    analyze_ai_txt,
)
from botaudit.models import Severity
from botaudit.recommendations import recommend_llm_discovery
from botaudit.robots_analysis import RobotsTxtResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_plugin_json(**overrides) -> str:
    """Return a valid ai-plugin.json string with optional field overrides."""
    data = {
        "schema_version": "v1",
        "name_for_human": "Example Plugin",
        "name_for_model": "example",
        "description_for_human": "An example plugin",
        "description_for_model": "An example plugin for AI models",
    }
    data.update(overrides)
    return json.dumps(data)


# ── SPEC-ai-metadata FR-2: ai.txt analysis ───────────────────────────────


class TestAnalyzeAiTxt(unittest.TestCase):
    """SPEC-ai-metadata FR-2 — ai.txt detection and validation."""

    def test_none_content_returns_not_present(self):
        result = analyze_ai_txt(None)
        self.assertFalse(result.present)
        self.assertEqual(result.line_count, 0)

    def test_empty_content_returns_not_present(self):
        result = analyze_ai_txt("")
        self.assertFalse(result.present)

    def test_whitespace_only_returns_not_present(self):
        result = analyze_ai_txt("   \n\n  ")
        self.assertFalse(result.present)

    def test_short_content_returns_not_present(self):
        """FR-2.2: <=10 chars after trim → not present."""
        result = analyze_ai_txt("short")
        self.assertFalse(result.present)

    def test_exactly_10_chars_not_present(self):
        """FR-2.2: exactly 10 chars → not present (must be >10)."""
        result = analyze_ai_txt("0123456789")
        self.assertFalse(result.present)

    def test_substantive_content_is_present(self):
        """FR-2.2: >10 chars after trim → present."""
        result = analyze_ai_txt("This is a valid ai.txt file")
        self.assertTrue(result.present)

    def test_line_count_reported(self):
        """FR-2.4: line_count reflects number of lines."""
        content = "line one\nline two\nline three\n"
        result = analyze_ai_txt(content)
        self.assertTrue(result.present)
        self.assertEqual(result.line_count, 3)


# ── SPEC-ai-metadata FR-3: ai-plugin.json analysis ───────────────────────


class TestAnalyzeAiPluginJson(unittest.TestCase):
    """SPEC-ai-metadata FR-3 — ai-plugin.json parsing and validation."""

    def test_none_content_returns_not_present(self):
        result = analyze_ai_plugin_json(None)
        self.assertFalse(result.present)
        self.assertFalse(result.valid)

    def test_invalid_json_returns_not_present(self):
        """FR-3.1: malformed JSON → not present."""
        result = analyze_ai_plugin_json("{bad json")
        self.assertFalse(result.present)

    def test_valid_manifest_all_required_fields(self):
        """FR-3.3: all required fields present and non-empty → valid."""
        result = analyze_ai_plugin_json(_valid_plugin_json())
        self.assertTrue(result.present)
        self.assertTrue(result.valid)

    def test_missing_required_field_is_invalid(self):
        """FR-3.2/FR-3.3: missing a required field → present but not valid."""
        data = json.loads(_valid_plugin_json())
        del data["name_for_model"]
        result = analyze_ai_plugin_json(json.dumps(data))
        self.assertTrue(result.present)
        self.assertFalse(result.valid)

    def test_empty_required_field_is_invalid(self):
        """FR-3.3: required field is empty string → not valid."""
        result = analyze_ai_plugin_json(_valid_plugin_json(schema_version=""))
        self.assertTrue(result.present)
        self.assertFalse(result.valid)

    def test_api_subfields_detected(self):
        """FR-3.4: api.type and api.url present → has_api is True."""
        result = analyze_ai_plugin_json(
            _valid_plugin_json(api={"type": "openapi", "url": "https://example.com/api"})
        )
        self.assertTrue(result.has_api)

    def test_api_missing_subfields(self):
        """FR-3.4: api present but missing type/url → has_api is False."""
        result = analyze_ai_plugin_json(_valid_plugin_json(api={"type": "openapi"}))
        self.assertFalse(result.has_api)

    def test_no_api_field(self):
        """FR-3.4: no api field → has_api is False."""
        result = analyze_ai_plugin_json(_valid_plugin_json())
        self.assertFalse(result.has_api)

    def test_name_fields_extracted(self):
        """FR-3.2: name_for_human and name_for_model extracted."""
        result = analyze_ai_plugin_json(_valid_plugin_json(
            name_for_human="My Plugin",
            name_for_model="my_plugin",
        ))
        self.assertEqual(result.name_for_human, "My Plugin")
        self.assertEqual(result.name_for_model, "my_plugin")

    def test_json_array_returns_not_present(self):
        """Non-object JSON → not present."""
        result = analyze_ai_plugin_json("[]")
        self.assertFalse(result.present)

    def test_invalid_names_not_extracted_when_invalid(self):
        """When invalid, name fields remain empty."""
        result = analyze_ai_plugin_json(_valid_plugin_json(schema_version=""))
        self.assertEqual(result.name_for_human, "")
        self.assertEqual(result.name_for_model, "")


# ── SPEC-ai-metadata FR-4: agent.json analysis ───────────────────────────


class TestAnalyzeAgentJson(unittest.TestCase):
    """SPEC-ai-metadata FR-4 — agent.json detection and validation."""

    def test_none_content_returns_not_present(self):
        result = analyze_agent_json(None)
        self.assertFalse(result.present)

    def test_invalid_json_returns_not_present(self):
        """FR-4.1: malformed JSON → not present."""
        result = analyze_agent_json("not json")
        self.assertFalse(result.present)

    def test_empty_object_returns_not_present(self):
        """FR-4.2: empty {} → not present."""
        result = analyze_agent_json("{}")
        self.assertFalse(result.present)

    def test_non_empty_object_is_present(self):
        """FR-4.2: non-empty JSON object → present."""
        result = analyze_agent_json('{"name": "agent"}')
        self.assertTrue(result.present)

    def test_json_array_returns_not_present(self):
        """FR-4.2: JSON array (not object) → not present."""
        result = analyze_agent_json('[1, 2, 3]')
        self.assertFalse(result.present)


# ── SPEC-ai-metadata FR-5: Revised scoring ───────────────────────────────


class TestRevisedScoring(unittest.TestCase):
    """SPEC-ai-metadata FR-5 — Scoring with AI metadata signals."""

    def _make_result(
        self,
        *,
        robots: RobotsTxtResult | None = None,
        llms_txt: LlmsTxtResult | None = None,
        llms_full_txt: LlmsFullTxtResult | None = None,
        ai_metadata: AIMetadataResult | None = None,
    ) -> LLMDiscoverabilityResult:
        return LLMDiscoverabilityResult(
            robots=robots or RobotsTxtResult(),
            llms_txt=llms_txt or LlmsTxtResult(),
            llms_full_txt=llms_full_txt or LlmsFullTxtResult(),
            ai_metadata=ai_metadata or AIMetadataResult(),
        )

    def test_baseline_no_files(self):
        """FR-5.9: no robots.txt + no discovery files = 30."""
        result = self._make_result()
        cat = score_llm_discovery(result)
        self.assertEqual(cat.score, 30.0)

    def test_ai_txt_present_awards_5_points(self):
        """FR-5.2: ai.txt present → +5 pts."""
        baseline = score_llm_discovery(self._make_result()).score
        with_ai_txt = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(ai_txt=AiTxtResult(present=True, line_count=10)),
        )).score
        self.assertEqual(with_ai_txt - baseline, 5.0)

    def test_manifest_present_awards_5_points(self):
        """FR-5.3: at least one manifest present → +5 pts."""
        baseline = score_llm_discovery(self._make_result()).score
        with_agent = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(agent_json=AgentJsonResult(present=True)),
        )).score
        # agent.json present awards both "present" (5) and "valid" (5) = 10
        self.assertEqual(with_agent - baseline, 10.0)

    def test_manifest_valid_awards_5_points(self):
        """FR-5.4: at least one manifest valid → +5 pts."""
        # plugin present but invalid: gets 5 (present) but not 5 (valid)
        with_invalid = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=False),
            ),
        )).score
        with_valid = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=True, name_for_human="X"),
            ),
        )).score
        self.assertEqual(with_valid - with_invalid, 5.0)

    def test_both_manifests_present_no_double_credit(self):
        """FR-5.3: both present → still only 5 pts for presence signal."""
        one = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(agent_json=AgentJsonResult(present=True)),
        )).score
        both = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=True, name_for_human="X"),
                agent_json=AgentJsonResult(present=True),
            ),
        )).score
        self.assertEqual(both, one)

    def test_both_manifests_valid_no_double_credit(self):
        """FR-5.4: both valid → still only 5 pts for validity signal."""
        one_valid = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=True, name_for_human="X"),
            ),
        )).score
        both_valid = score_llm_discovery(self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=True, name_for_human="X"),
                agent_json=AgentJsonResult(present=True),
            ),
        )).score
        self.assertEqual(both_valid, one_valid)

    def test_ai_metadata_independent_of_llms_txt(self):
        """FR-5.7: ai.txt/manifest signals awarded even without llms.txt."""
        result = self._make_result(
            llms_txt=LlmsTxtResult(present=False),
            ai_metadata=AIMetadataResult(
                ai_txt=AiTxtResult(present=True, line_count=5),
                agent_json=AgentJsonResult(present=True),
            ),
        )
        cat = score_llm_discovery(result)
        # 30 (baseline) + 5 (ai.txt) + 5 (manifest present) + 5 (manifest valid) = 45
        self.assertEqual(cat.score, 45.0)

    def test_restrictive_robots_caps_at_65(self):
        """FR-5.8: restrictive → max 65 pts."""
        llms = LlmsTxtResult(
            present=True, is_valid=True, has_h1=True, h1_text="P",
            has_blockquote=True, blockquote_text="A summary with more than five words here",
            summary_substantive=True, h2_count=2, resource_link_count=3, has_md_links=True,
        )
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True, classification="restrictive",
                blocked_agents=["GPTBot"], has_sitemap=True, tool_allowed=False,
            ),
            llms_txt=llms,
            llms_full_txt=LlmsFullTxtResult(present=True),
            ai_metadata=AIMetadataResult(
                ai_txt=AiTxtResult(present=True, line_count=10),
                ai_plugin_json=AiPluginJsonResult(present=True, valid=True, name_for_human="X"),
                agent_json=AgentJsonResult(present=True),
            ),
        )
        cat = score_llm_discovery(result)
        # Signal 1 (30) and signal 10 (5) score 0 → max 65
        self.assertLessEqual(cat.score, 65.0)

    def test_llms_txt_present_reduced_to_15(self):
        """FR-5.2: llms.txt present signal now 15 pts (was 20)."""
        without = score_llm_discovery(self._make_result(
            robots=RobotsTxtResult(present=True, classification="open"),
        )).score
        with_llms = score_llm_discovery(self._make_result(
            robots=RobotsTxtResult(present=True, classification="open"),
            llms_txt=LlmsTxtResult(present=True),
        )).score
        self.assertEqual(with_llms - without, 15.0)

    def test_resource_links_reduced_to_5(self):
        """FR-5.2: resource links signal now 5 pts (was 10)."""
        without = score_llm_discovery(self._make_result(
            llms_txt=LlmsTxtResult(present=True),
        )).score
        with_links = score_llm_discovery(self._make_result(
            llms_txt=LlmsTxtResult(present=True, h2_count=1, resource_link_count=2),
        )).score
        self.assertEqual(with_links - without, 5.0)

    def test_llms_full_txt_reduced_to_5(self):
        """FR-5.2: llms-full.txt signal now 5 pts (was 10)."""
        without = score_llm_discovery(self._make_result(
            llms_txt=LlmsTxtResult(present=True),
        )).score
        with_full = score_llm_discovery(self._make_result(
            llms_txt=LlmsTxtResult(present=True),
            llms_full_txt=LlmsFullTxtResult(present=True),
        )).score
        self.assertEqual(with_full - without, 5.0)

    def test_full_score_with_all_files(self):
        """All signals satisfied → 100 pts."""
        llms = LlmsTxtResult(
            present=True, is_valid=True, has_h1=True, h1_text="P",
            has_blockquote=True, blockquote_text="A summary with more than five words here",
            summary_substantive=True, h2_count=2, resource_link_count=3, has_md_links=True,
        )
        result = self._make_result(
            robots=RobotsTxtResult(
                present=True, classification="open",
                agent_statuses={"ClaudeBot": "allowed"},
                has_sitemap=True, tool_allowed=True,
            ),
            llms_txt=llms,
            llms_full_txt=LlmsFullTxtResult(present=True),
            ai_metadata=AIMetadataResult(
                ai_txt=AiTxtResult(present=True, line_count=10),
                ai_plugin_json=AiPluginJsonResult(present=True, valid=True, name_for_human="X"),
                agent_json=AgentJsonResult(present=True),
            ),
        )
        cat = score_llm_discovery(result)
        self.assertEqual(cat.score, 100.0)


# ── SPEC-ai-metadata FR-6: Findings ──────────────────────────────────────


class TestAIMetadataFindings(unittest.TestCase):
    """SPEC-ai-metadata FR-6 — Findings messages for AI metadata."""

    def _make_result(self, **kwargs) -> LLMDiscoverabilityResult:
        return LLMDiscoverabilityResult(
            robots=kwargs.get("robots", RobotsTxtResult()),
            llms_txt=kwargs.get("llms_txt", LlmsTxtResult()),
            llms_full_txt=kwargs.get("llms_full_txt", LlmsFullTxtResult()),
            ai_metadata=kwargs.get("ai_metadata", AIMetadataResult()),
        )

    def test_ai_txt_present_finding(self):
        """FR-6.1: 'ai.txt present (N lines).'"""
        result = self._make_result(
            ai_metadata=AIMetadataResult(ai_txt=AiTxtResult(present=True, line_count=15)),
        )
        cat = score_llm_discovery(result)
        self.assertTrue(any("ai.txt present (15 lines)" in f for f in cat.findings))

    def test_ai_txt_absent_finding(self):
        """FR-6.2: 'No ai.txt file found.'"""
        result = self._make_result()
        cat = score_llm_discovery(result)
        self.assertIn("No ai.txt file found.", cat.findings)

    def test_ai_plugin_json_valid_finding(self):
        """FR-6.3: 'ai-plugin.json present — valid plugin manifest (name: ...).'"""
        result = self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(
                    present=True, valid=True, name_for_human="Test Plugin",
                ),
            ),
        )
        cat = score_llm_discovery(result)
        self.assertTrue(any(
            'ai-plugin.json present' in f and 'Test Plugin' in f
            for f in cat.findings
        ))

    def test_ai_plugin_json_invalid_finding(self):
        """FR-6.4: 'ai-plugin.json present but missing required fields.'"""
        result = self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=False),
            ),
        )
        cat = score_llm_discovery(result)
        self.assertIn("ai-plugin.json present but missing required fields.", cat.findings)

    def test_ai_plugin_json_absent_finding(self):
        """FR-6.5: 'No ai-plugin.json found.'"""
        result = self._make_result()
        cat = score_llm_discovery(result)
        self.assertIn("No ai-plugin.json found.", cat.findings)

    def test_agent_json_present_finding(self):
        """FR-6.6: 'agent.json present.'"""
        result = self._make_result(
            ai_metadata=AIMetadataResult(agent_json=AgentJsonResult(present=True)),
        )
        cat = score_llm_discovery(result)
        self.assertIn("agent.json present.", cat.findings)

    def test_agent_json_absent_finding(self):
        """FR-6.7: 'No agent.json found.'"""
        result = self._make_result()
        cat = score_llm_discovery(result)
        self.assertIn("No agent.json found.", cat.findings)


# ── SPEC-ai-metadata FR-7: Recommendations ───────────────────────────────


class TestAIMetadataRecommendations(unittest.TestCase):
    """SPEC-ai-metadata FR-7 — Recommendations for AI metadata."""

    def _make_result(self, **kwargs) -> LLMDiscoverabilityResult:
        return LLMDiscoverabilityResult(
            robots=kwargs.get("robots", RobotsTxtResult(classification="open")),
            llms_txt=kwargs.get("llms_txt", LlmsTxtResult()),
            llms_full_txt=kwargs.get("llms_full_txt", LlmsFullTxtResult()),
            ai_metadata=kwargs.get("ai_metadata", AIMetadataResult()),
        )

    def test_absent_ai_txt_recommends_creation(self):
        """FR-7.1: absent ai.txt → LOW recommendation."""
        result = self._make_result()
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.LOW and "ai.txt" in r.message
            for r in recs
        ))

    def test_present_ai_txt_no_recommendation(self):
        """ai.txt present → no ai.txt recommendation."""
        result = self._make_result(
            ai_metadata=AIMetadataResult(ai_txt=AiTxtResult(present=True, line_count=5)),
        )
        recs = recommend_llm_discovery(result)
        self.assertFalse(any(
            "ai.txt" in r.message and "Create" in r.message
            for r in recs
        ))

    def test_no_manifests_recommends_ai_plugin(self):
        """FR-7.2: no ai-plugin.json or agent.json → LOW recommendation."""
        result = self._make_result()
        recs = recommend_llm_discovery(result)
        self.assertTrue(any(
            r.severity == Severity.LOW and "ai-plugin.json" in r.message
            for r in recs
        ))

    def test_manifest_present_no_creation_rec(self):
        """Manifest present → no creation recommendation."""
        result = self._make_result(
            ai_metadata=AIMetadataResult(agent_json=AgentJsonResult(present=True)),
        )
        recs = recommend_llm_discovery(result)
        self.assertFalse(any(
            "Create" in r.message and "ai-plugin.json" in r.message
            for r in recs
        ))

    def test_invalid_ai_plugin_recommends_fix(self):
        """FR-7.3: invalid ai-plugin.json → LOW, lists required fields."""
        result = self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=False),
            ),
        )
        recs = recommend_llm_discovery(result)
        fix_recs = [r for r in recs if r.severity == Severity.LOW and "missing required" in r.message]
        self.assertEqual(len(fix_recs), 1)
        for field_name in AI_PLUGIN_REQUIRED_FIELDS:
            self.assertIn(field_name, fix_recs[0].message)

    def test_valid_ai_plugin_no_fix_rec(self):
        """Valid ai-plugin.json → no fix recommendation."""
        result = self._make_result(
            ai_metadata=AIMetadataResult(
                ai_plugin_json=AiPluginJsonResult(present=True, valid=True, name_for_human="X"),
            ),
        )
        recs = recommend_llm_discovery(result)
        self.assertFalse(any("missing required" in r.message for r in recs))


# ── SPEC-ai-metadata FR-1: Content-Type validation ───────────────────────


class TestContentTypeValidation(unittest.TestCase):
    """SPEC-ai-metadata FR-1.6 / FR-1.7 — Content-Type checks."""

    def test_html_rejected_for_text_files(self):
        """FR-1.6: text/html → rejected by _is_text_content_type."""
        self.assertFalse(_is_text_content_type("text/html"))

    def test_html_rejected_for_json_files(self):
        """FR-1.7: text/html → rejected by _is_json_content_type."""
        self.assertFalse(_is_json_content_type("text/html"))

    def test_application_json_accepted(self):
        """FR-1.7: application/json accepted."""
        self.assertTrue(_is_json_content_type("application/json"))

    def test_application_json_with_charset_accepted(self):
        """FR-1.7: application/json; charset=utf-8 accepted."""
        self.assertTrue(_is_json_content_type("application/json; charset=utf-8"))

    def test_text_plain_accepted_for_text(self):
        """FR-1.6: text/plain accepted."""
        self.assertTrue(_is_text_content_type("text/plain"))

    def test_text_plain_accepted_for_json(self):
        """FR-1.7: text/plain also accepted for JSON files."""
        self.assertTrue(_is_json_content_type("text/plain"))

    def test_empty_content_type_rejected(self):
        """Empty content-type rejected."""
        self.assertFalse(_is_text_content_type(""))
        self.assertFalse(_is_json_content_type(""))


if __name__ == "__main__":
    unittest.main()
