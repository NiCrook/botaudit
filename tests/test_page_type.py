"""Tests for page-type detection heuristics (SPEC-page-type-heuristics)."""

import unittest

from botaudit.analysis import (
    AnalysisResult,
    ContentAvailabilityResult,
    JsonLdBlock,
    LinkDiscoverabilityResult,
    MetadataResult,
    SemanticHTMLResult,
    StructuredDataResult,
)
from botaudit.models import CategoryResult, Recommendation, Report, Severity
from botaudit.page_type import (
    MIN_CONFIDENCE_THRESHOLD,
    PAGE_TYPES,
    PageTypeResult,
    PageTypeSignal,
    detect_page_type,
)
from botaudit.recommendations import recommend


def _make_analysis(**kwargs) -> AnalysisResult:
    """Build a minimal AnalysisResult, overriding specific sub-results."""
    return AnalysisResult(
        semantic_html=kwargs.get("semantic_html", SemanticHTMLResult()),
        content_availability=kwargs.get(
            "content_availability", ContentAvailabilityResult(word_count=200)
        ),
        link_discoverability=kwargs.get(
            "link_discoverability", LinkDiscoverabilityResult()
        ),
        structured_data=kwargs.get("structured_data", StructuredDataResult()),
        metadata=kwargs.get("metadata", MetadataResult()),
    )


def _make_jsonld_block(type_value: str, **kwargs) -> JsonLdBlock:
    return JsonLdBlock(
        raw_valid=True,
        context_present=kwargs.get("context_present", True),
        type_value=type_value,
        recognized_type=kwargs.get("recognized_type", True),
        properties_present=kwargs.get("properties_present", []),
        properties_missing=kwargs.get("properties_missing", []),
    )


# -----------------------------------------------------------------------
# Detection tests
# -----------------------------------------------------------------------


class TestDetectArticle(unittest.TestCase):
    """Article detection from JSON-LD, og:type, URL, and HTML."""

    def test_article_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("Article")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "article")

    def test_newsarticle_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("NewsArticle")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "article")

    def test_blogposting_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("BlogPosting")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "article")

    def test_article_url_pattern(self):
        result = detect_page_type(_make_analysis(), "https://example.com/blog/my-post")
        # URL pattern alone gives 1.5, below threshold of 2.0 → generic
        self.assertEqual(result.page_type, "generic")

    def test_article_url_plus_html_signal(self):
        html = "<html><body><article><time>2024</time><p>Content</p></article></body></html>"
        result = detect_page_type(
            _make_analysis(), "https://example.com/blog/my-post", html=html
        )
        # URL (1.5) + article element (1.5) + time (0.5) = 3.5 for article → article
        self.assertEqual(result.page_type, "article")

    def test_article_og_type(self):
        html = '<html><head><meta property="og:type" content="article"></head><body></body></html>'
        result = detect_page_type(
            _make_analysis(), "https://example.com/blog/my-post", html=html
        )
        # URL (1.5) + og:type (2.0) = 3.5 → article
        self.assertEqual(result.page_type, "article")


class TestDetectProduct(unittest.TestCase):
    """Product detection."""

    def test_product_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("Product")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "product")

    def test_offer_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("Offer")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "product")

    def test_product_url(self):
        html = '<html><head><meta property="og:type" content="product"></head><body></body></html>'
        result = detect_page_type(
            _make_analysis(), "https://example.com/product/widget", html=html
        )
        # URL (1.5) + og:type (2.0) = 3.5 → product
        self.assertEqual(result.page_type, "product")


class TestDetectDocumentation(unittest.TestCase):
    """Documentation detection."""

    def test_docs_url_with_code(self):
        html = "<html><body><code>a</code><code>b</code><code>c</code></body></html>"
        result = detect_page_type(
            _make_analysis(), "https://example.com/docs/api-ref", html=html
        )
        # URL (1.5) + code elements (1.5) = 3.0 → documentation (medium)
        self.assertEqual(result.page_type, "documentation")

    def test_howto_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("HowTo")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "documentation")

    def test_faqpage_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("FAQPage")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "documentation")

    def test_headings_with_code(self):
        html = (
            "<html><body>"
            "<h2>A</h2><h2>B</h2><h2>C</h2><h3>D</h3><h3>E</h3>"
            "<code>x</code><pre>y</pre>"
            "</body></html>"
        )
        result = detect_page_type(
            _make_analysis(), "https://example.com/docs/guide", html=html
        )
        # URL (1.5) + headings+code (1.0) = 2.5 → documentation
        self.assertEqual(result.page_type, "documentation")


class TestDetectListing(unittest.TestCase):
    """Listing detection."""

    def test_itemlist_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("ItemList")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "listing")

    def test_collectionpage_jsonld(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("CollectionPage")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "listing")

    def test_breadcrumblist_alone_is_listing(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("BreadcrumbList")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        self.assertEqual(result.page_type, "listing")

    def test_breadcrumblist_suppressed_with_article(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[
                _make_jsonld_block("Article"),
                _make_jsonld_block("BreadcrumbList"),
            ],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        # BreadcrumbList suppressed; Article (3.0) wins
        self.assertEqual(result.page_type, "article")
        # Ensure no BreadcrumbList signal
        self.assertFalse(
            any(s.detail == "@type: BreadcrumbList" for s in result.signals)
        )


class TestDetectHomepage(unittest.TestCase):
    """Homepage detection."""

    def test_root_url(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("WebSite")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/")
        # WebSite (1.5) + root URL (3.0) = 4.5 → homepage
        self.assertEqual(result.page_type, "homepage")

    def test_root_url_alone(self):
        result = detect_page_type(_make_analysis(), "https://example.com/")
        self.assertEqual(result.page_type, "homepage")

    def test_index_html(self):
        result = detect_page_type(_make_analysis(), "https://example.com/index.html")
        self.assertEqual(result.page_type, "homepage")


class TestDetectGeneric(unittest.TestCase):
    """Generic fallback."""

    def test_no_signals(self):
        result = detect_page_type(_make_analysis(), "https://example.com/some/path")
        self.assertEqual(result.page_type, "generic")
        self.assertEqual(result.confidence, "none")

    def test_weak_single_signal_below_threshold(self):
        """A single URL pattern (1.5) is below MIN_CONFIDENCE_THRESHOLD (2.0)."""
        result = detect_page_type(_make_analysis(), "https://example.com/blog/my-post")
        self.assertEqual(result.page_type, "generic")


class TestConflictingSignals(unittest.TestCase):
    """Conflicting signals resolve to highest vote."""

    def test_product_schema_on_blog_url(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("Product")],
        )
        result = detect_page_type(
            _make_analysis(structured_data=sd), "https://example.com/blog/review"
        )
        # Product JSON-LD (3.0) > blog URL (1.5) → product wins
        self.assertEqual(result.page_type, "product")

    def test_multiple_signals_same_type_accumulate(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[
                _make_jsonld_block("Article"),
                _make_jsonld_block("Review"),
            ],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        # Article (3.0) + Review (3.0) = 6.0 for article → high confidence
        self.assertEqual(result.page_type, "article")
        self.assertEqual(result.confidence, "high")


# -----------------------------------------------------------------------
# Confidence tests
# -----------------------------------------------------------------------


class TestConfidence(unittest.TestCase):
    """FR-3.2: Confidence level computation."""

    def test_high_confidence(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("Article")],
        )
        html = "<html><body><article><time>2024</time>Long content</article></body></html>"
        result = detect_page_type(
            _make_analysis(structured_data=sd),
            "https://example.com/blog/post",
            html=html,
        )
        # Article JSON-LD (3.0) + URL (1.5) + article element (1.5) + time (0.5) = 6.5
        self.assertEqual(result.confidence, "high")

    def test_medium_confidence(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block("Product")],
        )
        result = detect_page_type(_make_analysis(structured_data=sd), "https://example.com/page")
        # Product JSON-LD (3.0) alone → medium (>= 2.0, ratio >= 0.4)
        self.assertEqual(result.confidence, "medium")

    def test_none_confidence_for_generic(self):
        result = detect_page_type(_make_analysis(), "https://example.com/page")
        self.assertEqual(result.confidence, "none")

    def test_override_confidence(self):
        pt = PageTypeResult(page_type="article", confidence="override")
        self.assertEqual(pt.confidence, "override")


# -----------------------------------------------------------------------
# URL pattern tests
# -----------------------------------------------------------------------


class TestURLPatterns(unittest.TestCase):
    """FR-2.4.6: URL path pattern matching."""

    def test_case_insensitive(self):
        result = detect_page_type(_make_analysis(), "https://example.com/DOCS/api")
        # /docs/ pattern matches /DOCS/ (lowercased)
        url_signals = [s for s in result.signals if s.source == "url_path"]
        # Only 1.5 vote, below threshold → generic, but signal still recorded
        self.assertTrue(any(s.type_vote == "documentation" for s in url_signals))

    def test_first_matching_pattern_wins(self):
        """If URL matches multiple groups, only first group contributes."""
        # /blog/ is checked before /category/
        result = detect_page_type(
            _make_analysis(), "https://example.com/blog/category/tech"
        )
        url_signals = [s for s in result.signals if s.source == "url_path"]
        self.assertEqual(len(url_signals), 1)
        self.assertEqual(url_signals[0].type_vote, "article")

    def test_empty_path_is_homepage(self):
        result = detect_page_type(_make_analysis(), "https://example.com")
        url_signals = [s for s in result.signals if s.source == "url_path"]
        self.assertTrue(any(s.type_vote == "homepage" for s in url_signals))


# -----------------------------------------------------------------------
# HTML structure signal tests
# -----------------------------------------------------------------------


class TestHTMLStructureSignals(unittest.TestCase):
    """FR-2.4.8: HTML element-based signals."""

    def test_article_element(self):
        html = "<html><body><article>Content here</article></body></html>"
        result = detect_page_type(
            _make_analysis(), "https://example.com/page", html=html
        )
        self.assertTrue(any(
            s.source == "html_structure" and s.type_vote == "article"
            for s in result.signals
        ))

    def test_code_elements_for_docs(self):
        html = "<html><body><code>a</code><code>b</code><pre>c</pre></body></html>"
        result = detect_page_type(
            _make_analysis(), "https://example.com/page", html=html
        )
        self.assertTrue(any(
            s.source == "html_structure" and s.type_vote == "documentation"
            for s in result.signals
        ))

    def test_high_word_count_with_article(self):
        analysis = _make_analysis(
            content_availability=ContentAvailabilityResult(word_count=600)
        )
        html = "<html><body><article>Content</article></body></html>"
        result = detect_page_type(analysis, "https://example.com/page", html=html)
        # Should have both <article> (1.5) and high-word-count+article (1.0)
        article_signals = [
            s for s in result.signals
            if s.source == "html_structure" and s.type_vote == "article"
        ]
        self.assertGreaterEqual(len(article_signals), 2)

    def test_list_items_with_links(self):
        links = "".join(
            f'<li><a href="/item/{i}">Item {i}</a></li>' for i in range(12)
        )
        html = f"<html><body><ul>{links}</ul></body></html>"
        analysis = _make_analysis(
            link_discoverability=LinkDiscoverabilityResult(navigable_links=12)
        )
        result = detect_page_type(analysis, "https://example.com/page", html=html)
        self.assertTrue(any(
            s.source == "html_structure" and s.type_vote == "listing"
            for s in result.signals
        ))

    def test_without_html_uses_semantic_breakdown(self):
        """When html is not provided, falls back to semantic_breakdown."""
        sem = SemanticHTMLResult(semantic_breakdown={"article": 1, "time": 2})
        result = detect_page_type(
            _make_analysis(semantic_html=sem), "https://example.com/page"
        )
        article_signals = [
            s for s in result.signals
            if s.source == "html_structure" and s.type_vote == "article"
        ]
        self.assertGreaterEqual(len(article_signals), 1)


# -----------------------------------------------------------------------
# Meta tag signal tests
# -----------------------------------------------------------------------


class TestMetaTagSignals(unittest.TestCase):
    """FR-2.4.10: pagetype meta tag."""

    def test_pagetype_meta(self):
        html = '<html><head><meta name="pagetype" content="article"></head><body></body></html>'
        result = detect_page_type(
            _make_analysis(), "https://example.com/page", html=html
        )
        self.assertTrue(any(
            s.source == "meta_tag" and s.type_vote == "article"
            for s in result.signals
        ))

    def test_pagetype_meta_docs(self):
        html = '<html><head><meta name="pagetype" content="docs"></head><body></body></html>'
        result = detect_page_type(
            _make_analysis(), "https://example.com/page", html=html
        )
        self.assertTrue(any(
            s.source == "meta_tag" and s.type_vote == "documentation"
            for s in result.signals
        ))


# -----------------------------------------------------------------------
# Type-aware recommendation tests
# -----------------------------------------------------------------------


class TestArticleRecommendations(unittest.TestCase):
    """FR-4.3: Article-specific recommendations."""

    def test_missing_article_schema(self):
        categories = [
            CategoryResult(name="Structured Data", score=50),
            CategoryResult(name="Semantic HTML", score=50),
        ]
        pt = PageTypeResult(page_type="article", confidence="high")
        result = recommend(_make_analysis(), categories, page_type=pt)
        sd_recs = [
            r for r in result[0].recommendations if r.message.startswith("[article]")
        ]
        self.assertTrue(any("Article schema" in r.message for r in sd_recs))

    def test_missing_article_element(self):
        categories = [
            CategoryResult(name="Structured Data", score=50),
            CategoryResult(name="Semantic HTML", score=50),
        ]
        pt = PageTypeResult(page_type="article", confidence="high")
        result = recommend(_make_analysis(), categories, page_type=pt)
        sem_recs = [
            r for r in result[1].recommendations if r.message.startswith("[article]")
        ]
        self.assertTrue(any("<article>" in r.message for r in sem_recs))

    def test_no_type_recs_when_score_above_threshold(self):
        """FR-4.4: No type-aware recs when category scores >= 90."""
        categories = [
            CategoryResult(name="Structured Data", score=95),
        ]
        pt = PageTypeResult(page_type="article", confidence="high")
        result = recommend(_make_analysis(), categories, page_type=pt)
        self.assertEqual(result[0].recommendations, [])

    def test_article_missing_datepublished(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block(
                "Article",
                properties_present=["headline", "author"],
                properties_missing=["datePublished"],
            )],
        )
        categories = [CategoryResult(name="Structured Data", score=50)]
        pt = PageTypeResult(page_type="article", confidence="high")
        result = recommend(
            _make_analysis(structured_data=sd), categories, page_type=pt
        )
        recs = [r for r in result[0].recommendations if "[article]" in r.message]
        self.assertTrue(any("datePublished" in r.message for r in recs))

    def test_article_missing_author(self):
        sd = StructuredDataResult(
            has_json_ld=True,
            json_ld_blocks=[_make_jsonld_block(
                "Article",
                properties_present=["headline", "datePublished"],
                properties_missing=["author"],
            )],
        )
        categories = [CategoryResult(name="Structured Data", score=50)]
        pt = PageTypeResult(page_type="article", confidence="high")
        result = recommend(
            _make_analysis(structured_data=sd), categories, page_type=pt
        )
        recs = [r for r in result[0].recommendations if "[article]" in r.message]
        self.assertTrue(any("author" in r.message for r in recs))


class TestProductRecommendations(unittest.TestCase):
    """FR-4.3: Product-specific recommendations."""

    def test_missing_product_schema(self):
        categories = [CategoryResult(name="Structured Data", score=50)]
        pt = PageTypeResult(page_type="product", confidence="high")
        result = recommend(_make_analysis(), categories, page_type=pt)
        recs = [r for r in result[0].recommendations if "[product]" in r.message]
        self.assertTrue(any("Product schema" in r.message for r in recs))


class TestDocumentationRecommendations(unittest.TestCase):
    """FR-4.3: Documentation-specific recommendations."""

    def test_low_word_count(self):
        analysis = _make_analysis(
            content_availability=ContentAvailabilityResult(word_count=50)
        )
        categories = [CategoryResult(name="Content Availability", score=50)]
        pt = PageTypeResult(page_type="documentation", confidence="medium")
        result = recommend(analysis, categories, page_type=pt)
        recs = [r for r in result[0].recommendations if "[documentation]" in r.message]
        self.assertTrue(any("substantive content" in r.message for r in recs))

    def test_missing_nav(self):
        categories = [CategoryResult(name="Semantic HTML", score=50)]
        pt = PageTypeResult(page_type="documentation", confidence="medium")
        result = recommend(_make_analysis(), categories, page_type=pt)
        recs = [r for r in result[0].recommendations if "[documentation]" in r.message]
        self.assertTrue(any("<nav>" in r.message for r in recs))


class TestHomepageRecommendations(unittest.TestCase):
    """FR-4.3: Homepage-specific recommendations."""

    def test_missing_website_schema(self):
        categories = [CategoryResult(name="Structured Data", score=50)]
        pt = PageTypeResult(page_type="homepage", confidence="high")
        result = recommend(_make_analysis(), categories, page_type=pt)
        recs = [r for r in result[0].recommendations if "[homepage]" in r.message]
        self.assertTrue(any("WebSite or Organization" in r.message for r in recs))

    def test_missing_canonical(self):
        categories = [CategoryResult(name="Metadata & Discoverability", score=50)]
        pt = PageTypeResult(page_type="homepage", confidence="high")
        result = recommend(_make_analysis(), categories, page_type=pt)
        recs = [r for r in result[0].recommendations if "[homepage]" in r.message]
        self.assertTrue(any("canonical" in r.message for r in recs))


class TestListingRecommendations(unittest.TestCase):
    """FR-4.3: Listing-specific recommendations."""

    def test_missing_itemlist_schema(self):
        categories = [CategoryResult(name="Structured Data", score=50)]
        pt = PageTypeResult(page_type="listing", confidence="medium")
        result = recommend(_make_analysis(), categories, page_type=pt)
        recs = [r for r in result[0].recommendations if "[listing]" in r.message]
        self.assertTrue(any("ItemList" in r.message for r in recs))


class TestGenericNoTypeRecs(unittest.TestCase):
    """Generic pages receive no type-aware recommendations."""

    def test_generic_no_extra_recs(self):
        categories = [CategoryResult(name="Structured Data", score=50)]
        pt = PageTypeResult(page_type="generic", confidence="none")
        result = recommend(_make_analysis(), categories, page_type=pt)
        type_recs = [
            r for r in result[0].recommendations
            if r.message.startswith("[")
        ]
        self.assertEqual(type_recs, [])


class TestRecommendPrefixes(unittest.TestCase):
    """FR-4.5: Type-aware recs prefixed with [type]."""

    def test_article_prefix(self):
        categories = [CategoryResult(name="Structured Data", score=50)]
        pt = PageTypeResult(page_type="article", confidence="high")
        result = recommend(_make_analysis(), categories, page_type=pt)
        type_recs = [
            r for r in result[0].recommendations
            if r.message.startswith("[article]")
        ]
        self.assertGreater(len(type_recs), 0)


# -----------------------------------------------------------------------
# CLI integration tests
# -----------------------------------------------------------------------


class TestCLIPageTypeArgs(unittest.TestCase):
    """FR-5, FR-6: CLI flag parsing."""

    def test_build_parser_has_page_type(self):
        from botaudit.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["https://example.com", "--page-type", "product"])
        self.assertEqual(args.page_type, "product")

    def test_build_parser_no_page_type(self):
        from botaudit.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["https://example.com", "--no-page-type"])
        self.assertTrue(args.no_page_type)

    def test_default_is_none(self):
        from botaudit.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["https://example.com"])
        self.assertIsNone(args.page_type)
        self.assertFalse(args.no_page_type)


# -----------------------------------------------------------------------
# Output format tests
# -----------------------------------------------------------------------


class TestTextOutput(unittest.TestCase):
    """FR-7.2: Page type in text output."""

    def test_page_type_in_text(self):
        from botaudit.report import format_report
        report = Report(
            url="https://example.com/blog/post",
            categories=[CategoryResult(name="Semantic HTML", score=80)],
            overall_score=80,
            grade="B",
            page_type=PageTypeResult(page_type="article", confidence="high"),
        )
        text = format_report(report)
        self.assertIn("Page type: article (high confidence)", text)

    def test_generic_page_type_in_text(self):
        from botaudit.report import format_report
        report = Report(
            url="https://example.com/page",
            categories=[CategoryResult(name="Semantic HTML", score=80)],
            overall_score=80,
            grade="B",
            page_type=PageTypeResult(page_type="generic", confidence="none"),
        )
        text = format_report(report)
        self.assertIn("Page type: generic", text)

    def test_override_in_text(self):
        from botaudit.report import format_report
        report = Report(
            url="https://example.com/page",
            categories=[CategoryResult(name="Semantic HTML", score=80)],
            overall_score=80,
            grade="B",
            page_type=PageTypeResult(page_type="product", confidence="override"),
        )
        text = format_report(report)
        self.assertIn("Page type: product (manual override)", text)

    def test_no_page_type_line_when_disabled(self):
        from botaudit.report import format_report
        report = Report(
            url="https://example.com/page",
            categories=[CategoryResult(name="Semantic HTML", score=80)],
            overall_score=80,
            grade="B",
        )
        text = format_report(report)
        self.assertNotIn("Page type:", text)


class TestJSONOutput(unittest.TestCase):
    """FR-7.3: page_type object in JSON output."""

    def test_page_type_in_json(self):
        import json
        from botaudit.report import format_json
        report = Report(
            url="https://example.com/blog/post",
            categories=[],
            overall_score=80,
            grade="B",
            page_type=PageTypeResult(
                page_type="article",
                confidence="high",
                signals=[PageTypeSignal("json_ld", "article", 3.0, "@type: Article")],
            ),
        )
        data = json.loads(format_json(report))
        self.assertIn("page_type", data)
        self.assertEqual(data["page_type"]["type"], "article")
        self.assertEqual(data["page_type"]["confidence"], "high")
        self.assertEqual(len(data["page_type"]["signals"]), 1)

    def test_no_page_type_when_disabled(self):
        import json
        from botaudit.report import format_json
        report = Report(
            url="https://example.com/page",
            categories=[],
            overall_score=80,
            grade="B",
        )
        data = json.loads(format_json(report))
        self.assertNotIn("page_type", data)


class TestCSVOutput(unittest.TestCase):
    """FR-7.7: page_type column in CSV."""

    def test_page_type_column(self):
        from botaudit.report import format_csv
        report = Report(
            url="https://example.com/page",
            categories=[CategoryResult(name="Semantic HTML", score=80)],
            overall_score=80,
            grade="B",
            page_type=PageTypeResult(page_type="article", confidence="high"),
        )
        csv_str = format_csv(report)
        lines = csv_str.strip().split("\n")
        header = lines[0]
        self.assertIn("page_type", header)
        self.assertIn("article", lines[1])

    def test_empty_page_type_when_disabled(self):
        from botaudit.report import format_csv
        report = Report(
            url="https://example.com/page",
            categories=[CategoryResult(name="Semantic HTML", score=80)],
            overall_score=80,
            grade="B",
        )
        csv_str = format_csv(report)
        lines = csv_str.strip().split("\n")
        # page_type column should be empty
        self.assertIn("page_type", lines[0])


class TestHTMLOutput(unittest.TestCase):
    """FR-7.8: Page type in HTML output."""

    def test_page_type_badge_in_html(self):
        from botaudit.report import format_html
        report = Report(
            url="https://example.com/page",
            categories=[],
            overall_score=80,
            grade="B",
            page_type=PageTypeResult(page_type="article", confidence="high"),
        )
        html = format_html(report)
        self.assertIn("page-type-badge", html)
        self.assertIn("article", html)

    def test_no_badge_for_generic(self):
        from botaudit.report import format_html
        report = Report(
            url="https://example.com/page",
            categories=[],
            overall_score=80,
            grade="B",
            page_type=PageTypeResult(page_type="generic", confidence="none"),
        )
        html = format_html(report)
        # Badge class exists in CSS but should not appear as an element in the body
        self.assertNotIn('<p class="page-type-badge">', html)


if __name__ == "__main__":
    unittest.main()
