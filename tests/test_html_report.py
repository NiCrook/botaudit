"""Tests for HTML report output (SPEC-html-report)."""

import unittest

from botaudit.batch import BatchResult, URLError, URLSuccess, format_batch_html
from botaudit.models import CategoryResult, Recommendation, Report, Severity
from botaudit.report import format_html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    url: str = "https://example.com",
    grade: str = "B",
    score: float = 82.0,
) -> Report:
    return Report(
        url=url,
        overall_score=score,
        grade=grade,
        categories=[
            CategoryResult(
                name="Content Availability",
                score=90.0,
                findings=["342 words of visible text."],
            ),
            CategoryResult(
                name="Semantic HTML",
                score=68.0,
                findings=["15 semantic vs 7 generic elements (ratio: 68%)"],
                recommendations=[
                    Recommendation(
                        message="Replace divs with semantic elements.",
                        severity=Severity.HIGH,
                        category="Semantic HTML",
                    ),
                ],
            ),
        ],
    )


def _make_batch(*specs: tuple) -> BatchResult:
    results = []
    for spec in specs:
        if len(spec) == 3:
            url, grade, score = spec
            results.append(URLSuccess(
                url=url,
                report=_make_report(url=url, grade=grade, score=score),
            ))
        else:
            url, msg = spec
            results.append(URLError(url=url, message=msg))
    return BatchResult(results=results)


# ===========================================================================
# FR-1 / FR-6 — HTML document structure
# ===========================================================================

class TestHtmlDocumentStructure(unittest.TestCase):
    """FR-6: Self-contained HTML5 document."""

    def setUp(self):
        self.html = format_html(_make_report())

    def test_doctype(self):
        """FR-6.1: Complete HTML5 document."""
        self.assertTrue(self.html.startswith("<!DOCTYPE html>"))

    def test_charset(self):
        """FR-6.4: UTF-8 charset declared."""
        self.assertIn('<meta charset="utf-8">', self.html)

    def test_viewport(self):
        """FR-7.4: Responsive viewport meta."""
        self.assertIn("viewport", self.html)

    def test_inline_css(self):
        """FR-6.1: CSS inlined in <style> block."""
        self.assertIn("<style>", self.html)

    def test_inline_js(self):
        """FR-6.1: JS inlined in <script> block."""
        self.assertIn("<script>", self.html)

    def test_no_external_links(self):
        """FR-6.2: No external stylesheet or script references."""
        self.assertNotIn("link rel=", self.html)
        self.assertNotIn('src="http', self.html)

    def test_system_fonts(self):
        """FR-7.5: System font stack, no external fonts."""
        self.assertIn("system-ui", self.html)

    def test_dark_mode(self):
        """FR-7.3: Dark mode media query present."""
        self.assertIn("prefers-color-scheme:dark", self.html)


# ===========================================================================
# FR-2 — Single-URL report content
# ===========================================================================

class TestHtmlSingleUrl(unittest.TestCase):
    """FR-2: Single-URL HTML report content."""

    def setUp(self):
        self.report = _make_report()
        self.html = format_html(self.report)

    def test_title(self):
        """FR-7.6: Title contains URL."""
        self.assertIn("<title>BotAudit Report", self.html)
        self.assertIn("https://example.com", self.html)

    def test_url_is_clickable_link(self):
        """FR-2.1: URL rendered as clickable link."""
        self.assertIn('href="https://example.com"', self.html)

    def test_grade_badge(self):
        """FR-2.1: Grade badge present with letter grade."""
        self.assertIn("grade-badge", self.html)
        self.assertIn(">B<", self.html)

    def test_overall_score(self):
        """FR-2.4: Score displayed as number."""
        self.assertIn("82/100", self.html)

    def test_categories_present(self):
        """FR-2.1: Category cards rendered."""
        self.assertIn("Content Availability", self.html)
        self.assertIn("Semantic HTML", self.html)

    def test_findings_rendered(self):
        """FR-2.2: Findings as list items."""
        self.assertIn("342 words of visible text.", self.html)

    def test_category_scores(self):
        """FR-2.1: Category scores displayed."""
        self.assertIn("90/100", self.html)
        self.assertIn("68/100", self.html)

    def test_category_weights(self):
        """FR-2.1: Category weights displayed."""
        self.assertIn("27%", self.html)
        self.assertIn("23%", self.html)

    def test_recommendations_present(self):
        """FR-2.3: Recommendations rendered."""
        self.assertIn("Replace divs with semantic elements.", self.html)
        self.assertIn("[HIGH]", self.html)

    def test_footer_present(self):
        """FR-2.1: Footer with timestamp and version."""
        self.assertIn("<footer>", self.html)
        self.assertIn("Generated by BotAudit", self.html)


# ===========================================================================
# FR-3 — Grade color coding
# ===========================================================================

class TestGradeColors(unittest.TestCase):
    """FR-3: Grade color coding."""

    def test_grade_a_green(self):
        html = format_html(_make_report(grade="A", score=95.0))
        self.assertIn("#22c55e", html)

    def test_grade_b_blue(self):
        html = format_html(_make_report(grade="B", score=85.0))
        self.assertIn("#3b82f6", html)

    def test_grade_c_yellow(self):
        html = format_html(_make_report(grade="C", score=75.0))
        self.assertIn("#eab308", html)

    def test_grade_d_orange(self):
        html = format_html(_make_report(grade="D", score=65.0))
        self.assertIn("#f97316", html)

    def test_grade_f_red(self):
        html = format_html(_make_report(grade="F", score=40.0))
        self.assertIn("#ef4444", html)


# ===========================================================================
# FR-8 — Recommendations suppression
# ===========================================================================

class TestHtmlRecommendations(unittest.TestCase):
    """FR-8: --no-recommendations handling."""

    def test_recommendations_included_by_default(self):
        """FR-8.2: Recommendations present when enabled."""
        html = format_html(_make_report(), show_recommendations=True)
        self.assertIn("Replace divs with semantic elements.", html)
        self.assertIn("Recommendations", html)

    def test_recommendations_omitted_from_dom(self):
        """FR-8.1: Recommendations absent from DOM when suppressed."""
        html = format_html(_make_report(), show_recommendations=False)
        self.assertNotIn("Replace divs with semantic elements.", html)
        self.assertNotIn("Recommendations", html)


# ===========================================================================
# NFR-3.2 — XSS prevention
# ===========================================================================

class TestHtmlEscaping(unittest.TestCase):
    """NFR-3.2: User content HTML-escaped."""

    def test_url_escaped(self):
        report = _make_report(url='https://example.com/a?b=1&c=<img src=x>')
        html = format_html(report)
        self.assertNotIn("<img src=x>", html)
        self.assertIn("&lt;img src=x&gt;", html)

    def test_findings_escaped(self):
        report = _make_report()
        report.categories[0].findings = ['<img onerror="alert(1)">']
        html = format_html(report)
        self.assertNotIn('onerror="alert(1)"', html)
        self.assertIn("&lt;img onerror=", html)


# ===========================================================================
# FR-4 — Batch HTML report
# ===========================================================================

class TestHtmlBatchReport(unittest.TestCase):
    """FR-4: Batch mode HTML report."""

    def setUp(self):
        self.batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "C", 72.0),
            ("https://fail.com", "Connection refused"),
        )
        self.html = format_batch_html(self.batch)

    def test_batch_title(self):
        """FR-7.6: Batch title with URL count."""
        self.assertIn("Batch (3 URLs)", self.html)

    def test_header_counts(self):
        """FR-4.1: Header shows total, success, failure counts."""
        self.assertIn("3 URLs audited", self.html)
        self.assertIn("2 succeeded", self.html)
        self.assertIn("1 failed", self.html)

    def test_summary_table_present(self):
        """FR-4.1: Summary table rendered."""
        self.assertIn("summary-table", self.html)

    def test_summary_table_sortable(self):
        """FR-4.1: Table headers have data-sort for JS sorting."""
        self.assertIn('data-sort="url"', self.html)
        self.assertIn('data-sort="grade"', self.html)
        self.assertIn('data-sort="score"', self.html)

    def test_summary_table_links_to_details(self):
        """FR-4.2: Table rows link to per-URL detail sections."""
        self.assertIn('href="#url-0"', self.html)

    def test_failed_url_shows_err(self):
        """FR-4.3: Failed URL shows ERR in summary table."""
        self.assertIn("ERR", self.html)

    def test_collapsible_details(self):
        """FR-4.5: Per-URL sections use <details>."""
        self.assertIn("url-detail", self.html)
        self.assertIn("<details", self.html)
        self.assertIn("<summary>", self.html)

    def test_no_detail_for_failed_url(self):
        """FR-4.4: Failed URLs have no detail section."""
        # There should be exactly 2 <details> elements (for the 2 successes)
        self.assertEqual(self.html.count('<details class="url-detail"'), 2)

    def test_expand_collapse_controls(self):
        """FR-4.6: Expand All / Collapse All buttons."""
        self.assertIn("expand-all", self.html)
        self.assertIn("collapse-all", self.html)

    def test_per_url_content(self):
        """FR-4.2: Detail sections contain full report content."""
        self.assertIn("Content Availability", self.html)
        self.assertIn("grade-badge", self.html)


# ===========================================================================
# FR-5 — Crawl metadata in batch HTML
# ===========================================================================

class TestHtmlCrawlMetadata(unittest.TestCase):
    """FR-5: Crawl metadata display."""

    def test_crawl_metadata_shown(self):
        """FR-5.1: Crawl summary rendered when crawl_result provided."""
        from dataclasses import dataclass

        @dataclass
        class FakeCrawlResult:
            origin: str = "https://example.com"
            sitemaps_found: int = 2
            urls_discovered: int = 150
            urls_after_filter: int = 148
            urls_after_limit: int = 50

        batch = _make_batch(("https://example.com", "B", 82.0))
        html = format_batch_html(batch, crawl_result=FakeCrawlResult())
        self.assertIn("crawl-meta", html)
        self.assertIn("https://example.com", html)
        self.assertIn("Sitemaps found: 2", html)
        self.assertIn("URLs discovered: 150", html)

    def test_no_crawl_metadata_without_result(self):
        """FR-5.1: No crawl section when crawl_result is None."""
        batch = _make_batch(("https://a.com", "A", 95.0))
        html = format_batch_html(batch, crawl_result=None)
        self.assertNotIn('<div class="crawl-meta">', html)


# ===========================================================================
# Batch recommendations suppression
# ===========================================================================

class TestHtmlBatchRecommendations(unittest.TestCase):
    """FR-8 in batch context."""

    def test_batch_recommendations_omitted(self):
        """FR-8.1: Recommendations absent from batch detail when suppressed."""
        batch = _make_batch(("https://a.com", "B", 82.0))
        html = format_batch_html(batch, show_recommendations=False)
        self.assertNotIn("Recommendations", html)


if __name__ == "__main__":
    unittest.main()
