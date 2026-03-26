"""Tests for SPEC-structured-data-validation — deeper structured data checks.

Covers: analysis (FR-1 through FR-6), scoring (FR-4), findings (FR-7),
and recommendations (FR-8).
"""

import json
import unittest

from bs4 import BeautifulSoup

from botaudit.analysis import (
    OG_RECOMMENDED,
    OG_REQUIRED,
    RECOGNIZED_SCHEMA_TYPES,
    SCHEMA_MIN_PROPERTIES,
    JsonLdBlock,
    StructuredDataResult,
    analyze_structured_data,
)
from botaudit.grading import score_structured_data
from botaudit.recommendations import recommend_structured_data
from botaudit.models import Severity


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _make_json_ld(obj: dict | list) -> str:
    return f'<script type="application/ld+json">{json.dumps(obj)}</script>'


# ── Minimal HTML builders ──────────────────────────────────────────

_VALID_ARTICLE = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Test",
    "author": "Alice",
    "datePublished": "2025-01-01",
}

_VALID_OG = (
    '<meta property="og:title" content="Title">'
    '<meta property="og:type" content="website">'
    '<meta property="og:image" content="https://example.com/img.png">'
    '<meta property="og:url" content="https://example.com">'
)

_VALID_OG_RECOMMENDED = (
    '<meta property="og:description" content="A description">'
    '<meta property="og:site_name" content="Example">'
)

_META_DESC_OPTIMAL = '<meta name="description" content="' + "x" * 100 + '">'
_META_DESC_SHORT = '<meta name="description" content="' + "x" * 30 + '">'
_META_DESC_LONG = '<meta name="description" content="' + "x" * 200 + '">'

_TWITTER = '<meta name="twitter:card" content="summary"><meta name="twitter:site" content="@test">'

_MICRODATA = '<div itemscope itemtype="https://schema.org/Product"><span itemprop="name">Widget</span></div>'


# ═══════════════════════════════════════════════════════════════════
# JSON-LD Analysis (FR-1)
# ═══════════════════════════════════════════════════════════════════


class TestJsonLdParsing(unittest.TestCase):
    """FR-1.1 — JSON-LD parsing and structure detection."""

    def test_valid_json_ld(self):
        html = _make_json_ld(_VALID_ARTICLE)
        r = analyze_structured_data(_soup(html))
        self.assertTrue(r.has_json_ld)
        self.assertEqual(r.json_ld_count, 1)
        self.assertEqual(r.json_ld_parseable_count, 1)

    def test_malformed_json(self):
        html = '<script type="application/ld+json">{not json}</script>'
        r = analyze_structured_data(_soup(html))
        self.assertTrue(r.has_json_ld)
        self.assertEqual(r.json_ld_parseable_count, 0)
        self.assertEqual(len(r.json_ld_blocks), 1)
        self.assertFalse(r.json_ld_blocks[0].raw_valid)

    def test_empty_object(self):
        html = _make_json_ld({})
        r = analyze_structured_data(_soup(html))
        self.assertTrue(r.has_json_ld)
        self.assertEqual(r.json_ld_parseable_count, 1)
        # No typed object — block still recorded
        self.assertEqual(len(r.json_ld_blocks), 1)
        self.assertTrue(r.json_ld_blocks[0].raw_valid)
        self.assertEqual(r.json_ld_blocks[0].type_value, "")

    def test_graph_array(self):
        data = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite", "name": "Test", "url": "https://example.com"},
                {"@type": "Person", "name": "Alice"},
            ],
        }
        html = _make_json_ld(data)
        r = analyze_structured_data(_soup(html))
        typed = [b for b in r.json_ld_blocks if b.type_value]
        self.assertEqual(len(typed), 2)
        types = {b.type_value for b in typed}
        self.assertEqual(types, {"WebSite", "Person"})
        # @context propagated from parent
        self.assertTrue(all(b.context_present for b in typed))

    def test_type_as_array(self):
        """FR-1.1.3 / NFR-2.3 — @type as array uses the first value."""
        data = {
            "@context": "https://schema.org",
            "@type": ["Article", "NewsArticle"],
            "headline": "Test",
            "author": "A",
            "datePublished": "2025-01-01",
        }
        html = _make_json_ld(data)
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.json_ld_blocks[0].type_value, "Article")

    def test_multiple_blocks(self):
        html = _make_json_ld(_VALID_ARTICLE) + _make_json_ld(
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": []}
        )
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.json_ld_count, 2)
        self.assertEqual(r.json_ld_parseable_count, 2)


class TestJsonLdContext(unittest.TestCase):
    """FR-1.2 — @context validation."""

    def test_https_schema_org(self):
        data = {"@context": "https://schema.org", "@type": "WebPage", "name": "T", "url": "u"}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertTrue(r.json_ld_blocks[0].context_present)

    def test_http_schema_org(self):
        data = {"@context": "http://schema.org", "@type": "WebPage", "name": "T", "url": "u"}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertTrue(r.json_ld_blocks[0].context_present)

    def test_trailing_slash_ok(self):
        data = {"@context": "https://schema.org/", "@type": "WebPage", "name": "T", "url": "u"}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertTrue(r.json_ld_blocks[0].context_present)

    def test_missing_context(self):
        data = {"@type": "Article", "headline": "Test"}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertFalse(r.json_ld_blocks[0].context_present)

    def test_context_as_array(self):
        data = {"@context": ["https://schema.org", {"@vocab": "http://example.com/"}], "@type": "Article"}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertTrue(r.json_ld_blocks[0].context_present)


class TestJsonLdProperties(unittest.TestCase):
    """FR-1.4 — Minimum recommended property validation."""

    def test_article_all_present(self):
        r = analyze_structured_data(_soup(_make_json_ld(_VALID_ARTICLE)))
        b = r.json_ld_blocks[0]
        self.assertEqual(b.properties_missing, [])
        self.assertCountEqual(b.properties_present, ["headline", "author", "datePublished"])

    def test_article_missing_author(self):
        data = {**_VALID_ARTICLE}
        del data["author"]
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        b = r.json_ld_blocks[0]
        self.assertIn("author", b.properties_missing)
        self.assertNotIn("author", b.properties_present)

    def test_property_empty_string_treated_absent(self):
        data = {**_VALID_ARTICLE, "headline": ""}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertIn("headline", r.json_ld_blocks[0].properties_missing)

    def test_property_null_treated_absent(self):
        data = {**_VALID_ARTICLE, "datePublished": None}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertIn("datePublished", r.json_ld_blocks[0].properties_missing)

    def test_property_empty_array_treated_absent(self):
        data = {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [],
        }
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        self.assertIn("itemListElement", r.json_ld_blocks[0].properties_missing)

    def test_unrecognized_type_no_property_check(self):
        data = {"@context": "https://schema.org", "@type": "CustomThing", "foo": "bar"}
        r = analyze_structured_data(_soup(_make_json_ld(data)))
        b = r.json_ld_blocks[0]
        self.assertFalse(b.recognized_type)
        self.assertEqual(b.properties_present, [])
        self.assertEqual(b.properties_missing, [])

    def test_recognized_types_constant(self):
        """All types in SCHEMA_MIN_PROPERTIES must be in RECOGNIZED_SCHEMA_TYPES."""
        for t in SCHEMA_MIN_PROPERTIES:
            self.assertIn(t, RECOGNIZED_SCHEMA_TYPES)


# ═══════════════════════════════════════════════════════════════════
# Open Graph Analysis (FR-2)
# ═══════════════════════════════════════════════════════════════════


class TestOpenGraph(unittest.TestCase):

    def test_all_required_present(self):
        r = analyze_structured_data(_soup(_VALID_OG))
        self.assertTrue(r.has_open_graph)
        self.assertEqual(r.og_required_missing, [])
        self.assertCountEqual(r.og_required_present, OG_REQUIRED)

    def test_missing_required(self):
        html = '<meta property="og:title" content="Title">'
        r = analyze_structured_data(_soup(html))
        self.assertTrue(r.has_open_graph)
        self.assertIn("og:type", r.og_required_missing)
        self.assertIn("og:image", r.og_required_missing)
        self.assertIn("og:url", r.og_required_missing)

    def test_empty_content_treated_absent(self):
        html = '<meta property="og:title" content=""><meta property="og:type" content="website">'
        r = analyze_structured_data(_soup(html))
        self.assertIn("og:title", r.og_required_missing)
        self.assertIn("og:title", r.open_graph_tags)  # tag exists, but content empty

    def test_recommended_present(self):
        html = _VALID_OG + _VALID_OG_RECOMMENDED
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.og_recommended_missing, [])
        self.assertCountEqual(r.og_recommended_present, OG_RECOMMENDED)

    def test_recommended_missing(self):
        r = analyze_structured_data(_soup(_VALID_OG))
        self.assertCountEqual(r.og_recommended_missing, OG_RECOMMENDED)

    def test_no_og_tags(self):
        r = analyze_structured_data(_soup("<html></html>"))
        self.assertFalse(r.has_open_graph)
        self.assertEqual(r.og_required_present, [])


# ═══════════════════════════════════════════════════════════════════
# Meta Description (FR-3)
# ═══════════════════════════════════════════════════════════════════


class TestMetaDescription(unittest.TestCase):

    def test_optimal_length(self):
        r = analyze_structured_data(_soup(_META_DESC_OPTIMAL))
        self.assertTrue(r.has_meta_description)
        self.assertEqual(r.meta_description_length, 100)
        self.assertEqual(r.meta_description_length_class, "optimal")

    def test_too_short(self):
        r = analyze_structured_data(_soup(_META_DESC_SHORT))
        self.assertEqual(r.meta_description_length, 30)
        self.assertEqual(r.meta_description_length_class, "too_short")

    def test_too_long(self):
        r = analyze_structured_data(_soup(_META_DESC_LONG))
        self.assertEqual(r.meta_description_length, 200)
        self.assertEqual(r.meta_description_length_class, "too_long")

    def test_boundary_49(self):
        html = '<meta name="description" content="' + "x" * 49 + '">'
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.meta_description_length_class, "too_short")

    def test_boundary_50(self):
        html = '<meta name="description" content="' + "x" * 50 + '">'
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.meta_description_length_class, "optimal")

    def test_boundary_160(self):
        html = '<meta name="description" content="' + "x" * 160 + '">'
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.meta_description_length_class, "optimal")

    def test_boundary_161(self):
        html = '<meta name="description" content="' + "x" * 161 + '">'
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.meta_description_length_class, "too_long")

    def test_absent(self):
        r = analyze_structured_data(_soup("<html></html>"))
        self.assertFalse(r.has_meta_description)
        self.assertEqual(r.meta_description_length, 0)
        self.assertEqual(r.meta_description_length_class, "")


# ═══════════════════════════════════════════════════════════════════
# Twitter Cards (FR-5)
# ═══════════════════════════════════════════════════════════════════


class TestTwitterCards(unittest.TestCase):

    def test_name_variant(self):
        html = '<meta name="twitter:card" content="summary">'
        r = analyze_structured_data(_soup(html))
        self.assertTrue(r.has_twitter_cards)
        self.assertIn("twitter:card", r.twitter_card_tags)

    def test_property_variant(self):
        html = '<meta property="twitter:card" content="summary">'
        r = analyze_structured_data(_soup(html))
        self.assertTrue(r.has_twitter_cards)

    def test_empty_content_ignored(self):
        html = '<meta name="twitter:card" content="">'
        r = analyze_structured_data(_soup(html))
        self.assertFalse(r.has_twitter_cards)

    def test_absent(self):
        r = analyze_structured_data(_soup("<html></html>"))
        self.assertFalse(r.has_twitter_cards)


# ═══════════════════════════════════════════════════════════════════
# Microdata (FR-6)
# ═══════════════════════════════════════════════════════════════════


class TestMicrodata(unittest.TestCase):

    def test_present(self):
        r = analyze_structured_data(_soup(_MICRODATA))
        self.assertTrue(r.has_microdata)
        self.assertEqual(r.microdata_count, 1)
        self.assertIn("https://schema.org/Product", r.microdata_types)

    def test_absent(self):
        r = analyze_structured_data(_soup("<html></html>"))
        self.assertFalse(r.has_microdata)
        self.assertEqual(r.microdata_count, 0)

    def test_multiple_itemscopes(self):
        html = (
            '<div itemscope itemtype="https://schema.org/Product"></div>'
            '<div itemscope itemtype="https://schema.org/Organization"></div>'
        )
        r = analyze_structured_data(_soup(html))
        self.assertEqual(r.microdata_count, 2)


# ═══════════════════════════════════════════════════════════════════
# Scoring (FR-4)
# ═══════════════════════════════════════════════════════════════════


class TestScoring(unittest.TestCase):

    def test_empty_page_scores_zero(self):
        r = analyze_structured_data(_soup("<html></html>"))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 0.0)

    def test_full_marks(self):
        """Page with all signals present scores exactly 100."""
        html = (
            _make_json_ld(_VALID_ARTICLE)
            + _VALID_OG
            + _VALID_OG_RECOMMENDED
            + _META_DESC_OPTIMAL
            + _TWITTER
            + _MICRODATA
        )
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 100.0)

    def test_json_ld_presence_only(self):
        """Empty JSON-LD {} — present (10) + parseable (5) = 15."""
        html = _make_json_ld({})
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 15.0)

    def test_json_ld_malformed(self):
        """Malformed JSON-LD — present (10) only."""
        html = '<script type="application/ld+json">{bad json}</script>'
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 10.0)

    def test_json_ld_full(self):
        """Valid Article with all properties: 10+5+5+5+10 = 35."""
        html = _make_json_ld(_VALID_ARTICLE)
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 35.0)

    def test_og_present_incomplete(self):
        """One OG tag with content: present (10) only."""
        html = '<meta property="og:title" content="Title">'
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 10.0)

    def test_og_required_complete(self):
        """All required OG: present (10) + required (10) = 20."""
        r = analyze_structured_data(_soup(_VALID_OG))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 20.0)

    def test_og_all(self):
        """All required + recommended OG: 10 + 10 + 5 = 25."""
        html = _VALID_OG + _VALID_OG_RECOMMENDED
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 25.0)

    def test_meta_desc_present_optimal(self):
        """Meta desc optimal: 10 + 5 = 15."""
        r = analyze_structured_data(_soup(_META_DESC_OPTIMAL))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 15.0)

    def test_meta_desc_present_suboptimal(self):
        """Meta desc too short: 10 only."""
        r = analyze_structured_data(_soup(_META_DESC_SHORT))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 10.0)

    def test_twitter_cards(self):
        r = analyze_structured_data(_soup(_TWITTER))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 5.0)

    def test_microdata(self):
        r = analyze_structured_data(_soup(_MICRODATA))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 5.0)

    def test_multi_format_bonus_two_formats(self):
        """JSON-LD + OG = 2 formats → bonus awarded."""
        html = _make_json_ld(_VALID_ARTICLE) + _VALID_OG
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        # JSON-LD: 35, OG required: 20, bonus: 15 = 70
        self.assertEqual(cat.score, 70.0)

    def test_multi_format_bonus_not_awarded_for_one(self):
        """Single format — no bonus."""
        html = _make_json_ld(_VALID_ARTICLE)
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 35.0)

    def test_meta_desc_only_max_15(self):
        """FR-4.5 — Only meta desc → max 15 points."""
        r = analyze_structured_data(_soup(_META_DESC_OPTIMAL))
        cat = score_structured_data(r)
        self.assertEqual(cat.score, 15.0)


# ═══════════════════════════════════════════════════════════════════
# Findings (FR-7)
# ═══════════════════════════════════════════════════════════════════


class TestFindings(unittest.TestCase):

    def test_json_ld_types_listed(self):
        html = _make_json_ld(_VALID_ARTICLE)
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertTrue(any("Article" in f for f in cat.findings))

    def test_json_ld_parse_failure_finding(self):
        html = '<script type="application/ld+json">{bad}</script>'
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertTrue(any("failed to parse" in f for f in cat.findings))

    def test_missing_context_finding(self):
        data = {"@type": "Article", "headline": "Test"}
        html = _make_json_ld(data)
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertTrue(any("@context" in f for f in cat.findings))

    def test_missing_properties_finding(self):
        data = {"@context": "https://schema.org", "@type": "Article"}
        html = _make_json_ld(data)
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertTrue(any("missing recommended properties" in f for f in cat.findings))

    def test_all_properties_finding(self):
        html = _make_json_ld(_VALID_ARTICLE)
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertTrue(any("has all recommended properties" in f for f in cat.findings))

    def test_og_complete_finding(self):
        r = analyze_structured_data(_soup(_VALID_OG))
        cat = score_structured_data(r)
        self.assertTrue(any("all required properties present" in f for f in cat.findings))

    def test_og_missing_required_finding(self):
        html = '<meta property="og:title" content="Title">'
        r = analyze_structured_data(_soup(html))
        cat = score_structured_data(r)
        self.assertTrue(any("missing required" in f for f in cat.findings))

    def test_meta_desc_optimal_finding(self):
        r = analyze_structured_data(_soup(_META_DESC_OPTIMAL))
        cat = score_structured_data(r)
        self.assertTrue(any("optimal length" in f for f in cat.findings))

    def test_meta_desc_too_short_finding(self):
        r = analyze_structured_data(_soup(_META_DESC_SHORT))
        cat = score_structured_data(r)
        self.assertTrue(any("below recommended minimum" in f for f in cat.findings))

    def test_meta_desc_too_long_finding(self):
        r = analyze_structured_data(_soup(_META_DESC_LONG))
        cat = score_structured_data(r)
        self.assertTrue(any("exceeds recommended maximum" in f for f in cat.findings))

    def test_no_json_ld_finding(self):
        r = analyze_structured_data(_soup("<html></html>"))
        cat = score_structured_data(r)
        self.assertTrue(any("No JSON-LD found" in f for f in cat.findings))

    def test_no_og_finding(self):
        r = analyze_structured_data(_soup("<html></html>"))
        cat = score_structured_data(r)
        self.assertTrue(any("No Open Graph tags found" in f for f in cat.findings))

    def test_no_meta_desc_finding(self):
        r = analyze_structured_data(_soup("<html></html>"))
        cat = score_structured_data(r)
        self.assertTrue(any("No meta description found" in f for f in cat.findings))

    def test_twitter_card_finding(self):
        r = analyze_structured_data(_soup(_TWITTER))
        cat = score_structured_data(r)
        self.assertTrue(any("Twitter Card tags present" in f for f in cat.findings))

    def test_no_twitter_finding(self):
        r = analyze_structured_data(_soup("<html></html>"))
        cat = score_structured_data(r)
        self.assertTrue(any("No Twitter Card tags found" in f for f in cat.findings))

    def test_microdata_finding(self):
        r = analyze_structured_data(_soup(_MICRODATA))
        cat = score_structured_data(r)
        self.assertTrue(any("Microdata present" in f for f in cat.findings))

    def test_no_microdata_finding(self):
        r = analyze_structured_data(_soup("<html></html>"))
        cat = score_structured_data(r)
        self.assertTrue(any("No microdata found" in f for f in cat.findings))


# ═══════════════════════════════════════════════════════════════════
# Recommendations (FR-8)
# ═══════════════════════════════════════════════════════════════════


class TestRecommendations(unittest.TestCase):

    def test_missing_json_ld_high(self):
        r = analyze_structured_data(_soup("<html></html>"))
        recs = recommend_structured_data(r)
        json_ld_recs = [r for r in recs if "JSON-LD" in r.message]
        self.assertTrue(any(r.severity == Severity.HIGH for r in json_ld_recs))

    def test_unparseable_json_ld_high(self):
        html = '<script type="application/ld+json">{bad}</script>'
        r = analyze_structured_data(_soup(html))
        recs = recommend_structured_data(r)
        self.assertTrue(any("invalid JSON" in r.message and r.severity == Severity.HIGH for r in recs))

    def test_missing_context_medium(self):
        data = {"@type": "Article", "headline": "Test"}
        html = _make_json_ld(data)
        r = analyze_structured_data(_soup(html))
        recs = recommend_structured_data(r)
        self.assertTrue(any("@context" in r.message and r.severity == Severity.MEDIUM for r in recs))

    def test_missing_properties_medium(self):
        data = {"@context": "https://schema.org", "@type": "Product"}
        html = _make_json_ld(data)
        r = analyze_structured_data(_soup(html))
        recs = recommend_structured_data(r)
        self.assertTrue(any("name" in r.message and r.severity == Severity.MEDIUM for r in recs))

    def test_missing_og_medium(self):
        r = analyze_structured_data(_soup("<html></html>"))
        recs = recommend_structured_data(r)
        self.assertTrue(any("Open Graph" in r.message and r.severity == Severity.MEDIUM for r in recs))

    def test_incomplete_og_medium(self):
        html = '<meta property="og:title" content="Title">'
        r = analyze_structured_data(_soup(html))
        recs = recommend_structured_data(r)
        self.assertTrue(any("missing required properties" in r.message for r in recs))

    def test_missing_meta_desc_medium(self):
        r = analyze_structured_data(_soup("<html></html>"))
        recs = recommend_structured_data(r)
        self.assertTrue(any("description" in r.message.lower() and r.severity == Severity.MEDIUM for r in recs))

    def test_short_meta_desc_low(self):
        r = analyze_structured_data(_soup(_META_DESC_SHORT))
        recs = recommend_structured_data(r)
        self.assertTrue(any("50–160" in r.message and r.severity == Severity.LOW for r in recs))

    def test_long_meta_desc_low(self):
        r = analyze_structured_data(_soup(_META_DESC_LONG))
        recs = recommend_structured_data(r)
        self.assertTrue(any("trimming" in r.message and r.severity == Severity.LOW for r in recs))

    def test_single_format_suggest_more_low(self):
        html = _make_json_ld(_VALID_ARTICLE)
        r = analyze_structured_data(_soup(html))
        recs = recommend_structured_data(r)
        self.assertTrue(any("second format" in r.message and r.severity == Severity.LOW for r in recs))

    def test_no_multi_format_rec_when_two_formats(self):
        html = _make_json_ld(_VALID_ARTICLE) + _VALID_OG
        r = analyze_structured_data(_soup(html))
        recs = recommend_structured_data(r)
        self.assertFalse(any("second format" in r.message for r in recs))

    def test_valid_page_minimal_recs(self):
        """A fully valid page should only get low-severity recs at most."""
        html = (
            _make_json_ld(_VALID_ARTICLE)
            + _VALID_OG
            + _VALID_OG_RECOMMENDED
            + _META_DESC_OPTIMAL
            + _TWITTER
            + _MICRODATA
        )
        r = analyze_structured_data(_soup(html))
        recs = recommend_structured_data(r)
        high = [r for r in recs if r.severity == Severity.HIGH]
        medium = [r for r in recs if r.severity == Severity.MEDIUM]
        self.assertEqual(len(high), 0)
        self.assertEqual(len(medium), 0)


if __name__ == "__main__":
    unittest.main()
