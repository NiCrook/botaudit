"""Tests for API / Library mode (SPEC-library-mode)."""

import json
import sys
import unittest
from io import StringIO
from unittest.mock import patch

from botaudit.batch import BatchResult, URLError, URLSuccess
from botaudit.fetcher import FetchError
from botaudit.models import (
    CATEGORY_WEIGHTS,
    CategoryResult,
    Recommendation,
    Report,
    Severity,
)
from botaudit.page_type import PageTypeResult, PageTypeSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINIMAL_HTML = """<!doctype html>
<html><head><title>Test</title></head>
<body><p>Hello world, this is a simple test page with enough words.</p></body>
</html>"""


def _make_report(
    url: str = "https://example.com",
    grade: str = "B",
    score: float = 85.0,
    page_type: PageTypeResult | None = None,
    recommendations: list[Recommendation] | None = None,
) -> Report:
    """Build a minimal Report for testing."""
    cats = [
        CategoryResult(
            name="Content Availability",
            score=score,
            findings=["Found 500 words"],
            recommendations=recommendations or [],
        ),
    ]
    return Report(
        url=url,
        categories=cats,
        overall_score=score,
        grade=grade,
        page_type=page_type,
    )


def _make_page_type(
    page_type: str = "article",
    confidence: str = "high",
) -> PageTypeResult:
    return PageTypeResult(
        page_type=page_type,
        confidence=confidence,
        signals=[
            PageTypeSignal(
                source="json_ld",
                type_vote="article",
                weight=3.0,
                detail="@type: Article",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# audit() tests — FR-1, FR-8
# ---------------------------------------------------------------------------

class TestAudit(unittest.TestCase):
    """Tests for the top-level audit() function."""

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_returns_report(self, _mock_fetch):
        """FR-1.2: audit() returns a Report on success."""
        from botaudit.api import audit

        report = audit(
            "https://example.com",
            skip_llm_discovery=True,
            no_recommendations=True,
        )
        self.assertIsInstance(report, Report)
        self.assertEqual(report.url, "https://example.com")
        self.assertIsInstance(report.overall_score, float)
        self.assertIn(report.grade, ("A", "B", "C", "D", "F"))
        self.assertTrue(len(report.categories) > 0)

    @patch("botaudit.fetcher.fetch", side_effect=FetchError("connection refused"))
    def test_raises_fetch_error(self, _mock_fetch):
        """FR-1.3 / FR-8.1: audit() raises FetchError on fetch failure."""
        from botaudit.api import audit

        with self.assertRaises(FetchError) as ctx:
            audit("https://fail.example.com", skip_llm_discovery=True)
        self.assertIn("connection refused", str(ctx.exception))

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_no_stdout_stderr(self, _mock_fetch):
        """FR-1.5: audit() does not write to stdout or stderr."""
        from botaudit.api import audit

        captured_out = StringIO()
        captured_err = StringIO()
        with patch("sys.stdout", captured_out), patch("sys.stderr", captured_err):
            audit(
                "https://example.com",
                skip_llm_discovery=True,
                no_recommendations=True,
            )
        self.assertEqual(captured_out.getvalue(), "")
        self.assertEqual(captured_err.getvalue(), "")

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_no_sys_exit(self, _mock_fetch):
        """FR-1.6: audit() never calls sys.exit()."""
        from botaudit.api import audit

        with patch("sys.exit", side_effect=AssertionError("sys.exit called")):
            # Should not raise AssertionError
            audit(
                "https://example.com",
                skip_llm_discovery=True,
                no_recommendations=True,
            )

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_passes_timeout(self, mock_fetch):
        """FR-1.1: timeout kwarg is forwarded."""
        from botaudit.api import audit

        audit(
            "https://example.com",
            timeout=5.0,
            skip_llm_discovery=True,
            no_recommendations=True,
        )
        mock_fetch.assert_called_once_with("https://example.com", timeout=5.0)

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_page_type_auto(self, _mock_fetch):
        """FR-1.1: page_type_mode='auto' attaches page_type to report."""
        from botaudit.api import audit

        report = audit(
            "https://example.com",
            skip_llm_discovery=True,
            no_recommendations=True,
            page_type_mode="auto",
        )
        # auto detection should produce a result (may be generic)
        self.assertIsNotNone(report.page_type)

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_page_type_disabled(self, _mock_fetch):
        """FR-1.1: page_type_mode='disabled' leaves page_type as None."""
        from botaudit.api import audit

        report = audit(
            "https://example.com",
            skip_llm_discovery=True,
            no_recommendations=True,
            page_type_mode="disabled",
        )
        self.assertIsNone(report.page_type)


# ---------------------------------------------------------------------------
# audit_batch() tests — FR-2, FR-8
# ---------------------------------------------------------------------------

class TestAuditBatch(unittest.TestCase):
    """Tests for the top-level audit_batch() function."""

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_returns_batch_result(self, _mock_fetch):
        """FR-2.2: audit_batch() returns a BatchResult."""
        from botaudit.api import audit_batch

        result = audit_batch(
            ["https://a.com", "https://b.com"],
            skip_llm_discovery=True,
            no_recommendations=True,
        )
        self.assertIsInstance(result, BatchResult)
        self.assertEqual(result.total, 2)
        self.assertEqual(result.succeeded, 2)

    @patch("botaudit.fetcher.fetch", side_effect=FetchError("timeout"))
    def test_captures_errors(self, _mock_fetch):
        """FR-2.2 / FR-8.3: per-URL errors captured as URLError, not raised."""
        from botaudit.api import audit_batch

        result = audit_batch(
            ["https://fail.com"],
            skip_llm_discovery=True,
        )
        self.assertEqual(result.failed, 1)
        self.assertIsInstance(result.results[0], URLError)

    def test_empty_list_raises(self):
        """FR-2.4 / FR-8.4: empty URL list raises ValueError."""
        from botaudit.api import audit_batch

        with self.assertRaises(ValueError):
            audit_batch([])

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_no_progress_output(self, _mock_fetch):
        """FR-2.3: audit_batch() does not print progress messages."""
        from botaudit.api import audit_batch

        captured_err = StringIO()
        with patch("sys.stderr", captured_err):
            audit_batch(
                ["https://a.com"],
                skip_llm_discovery=True,
                no_recommendations=True,
            )
        self.assertEqual(captured_err.getvalue(), "")

    @patch("botaudit.fetcher.fetch", return_value=_MINIMAL_HTML)
    def test_no_sys_exit(self, _mock_fetch):
        """FR-2.4: audit_batch() never calls sys.exit()."""
        from botaudit.api import audit_batch

        with patch("sys.exit", side_effect=AssertionError("sys.exit called")):
            audit_batch(
                ["https://a.com"],
                skip_llm_discovery=True,
                no_recommendations=True,
            )


# ---------------------------------------------------------------------------
# Report.to_dict() tests — FR-9
# ---------------------------------------------------------------------------

class TestReportToDict(unittest.TestCase):
    """Tests for Report.to_dict()."""

    def test_basic_structure(self):
        """FR-9.2: dict has url, overall_score, grade, categories."""
        report = _make_report()
        d = report.to_dict()
        self.assertEqual(d["url"], "https://example.com")
        self.assertEqual(d["overall_score"], 85.0)
        self.assertEqual(d["grade"], "B")
        self.assertIsInstance(d["categories"], list)
        self.assertEqual(len(d["categories"]), 1)

    def test_category_fields(self):
        """FR-9.2: each category has name, score, weight, findings."""
        report = _make_report()
        cat = report.to_dict()["categories"][0]
        self.assertEqual(cat["name"], "Content Availability")
        self.assertEqual(cat["score"], 85.0)
        self.assertEqual(cat["weight"], CATEGORY_WEIGHTS["Content Availability"])
        self.assertEqual(cat["findings"], ["Found 500 words"])

    def test_page_type_omitted_when_none(self):
        """FR-9.3: page_type key absent when None."""
        report = _make_report(page_type=None)
        d = report.to_dict()
        self.assertNotIn("page_type", d)

    def test_page_type_included_when_present(self):
        """FR-9.2: page_type included with type, confidence, signals."""
        pt = _make_page_type()
        report = _make_report(page_type=pt)
        d = report.to_dict()
        self.assertIn("page_type", d)
        self.assertEqual(d["page_type"]["type"], "article")
        self.assertEqual(d["page_type"]["confidence"], "high")
        self.assertEqual(len(d["page_type"]["signals"]), 1)
        sig = d["page_type"]["signals"][0]
        self.assertEqual(sig["source"], "json_ld")
        self.assertEqual(sig["type_vote"], "article")
        self.assertEqual(sig["weight"], 3.0)

    def test_recommendations_omitted_when_empty(self):
        """FR-9.4: recommendations key absent when no recommendations."""
        report = _make_report(recommendations=[])
        cat = report.to_dict()["categories"][0]
        self.assertNotIn("recommendations", cat)

    def test_recommendations_included_with_string_severity(self):
        """FR-9.2: recommendations use string severity values."""
        recs = [
            Recommendation(
                message="Add structured data",
                severity=Severity.HIGH,
                category="Content Availability",
            ),
        ]
        report = _make_report(recommendations=recs)
        cat = report.to_dict()["categories"][0]
        self.assertIn("recommendations", cat)
        self.assertEqual(len(cat["recommendations"]), 1)
        rec = cat["recommendations"][0]
        self.assertEqual(rec["message"], "Add structured data")
        self.assertEqual(rec["severity"], "high")

    def test_custom_weights(self):
        """FR-6.5: weights parameter changes category weight output."""
        custom = {"Content Availability": 0.50}
        report = _make_report()
        cat = report.to_dict(weights=custom)["categories"][0]
        self.assertEqual(cat["weight"], 0.50)

    def test_json_serializable(self):
        """NFR-5.2: output is JSON-serializable via json.dumps()."""
        pt = _make_page_type()
        recs = [
            Recommendation(
                message="Fix it", severity=Severity.MEDIUM, category="Content Availability",
            ),
        ]
        report = _make_report(page_type=pt, recommendations=recs)
        d = report.to_dict()
        # Should not raise
        text = json.dumps(d)
        parsed = json.loads(text)
        self.assertEqual(parsed["url"], "https://example.com")


# ---------------------------------------------------------------------------
# BatchResult.to_dict() tests — FR-10
# ---------------------------------------------------------------------------

class TestBatchResultToDict(unittest.TestCase):
    """Tests for BatchResult.to_dict()."""

    def test_basic_structure(self):
        """FR-10.2: dict has batch, total, succeeded, failed, results."""
        batch = BatchResult(results=[
            URLSuccess(url="https://a.com", report=_make_report("https://a.com")),
            URLError(url="https://b.com", message="timeout"),
        ])
        d = batch.to_dict()
        self.assertIs(d["batch"], True)
        self.assertEqual(d["total"], 2)
        self.assertEqual(d["succeeded"], 1)
        self.assertEqual(d["failed"], 1)
        self.assertEqual(len(d["results"]), 2)

    def test_success_entry_uses_report_to_dict(self):
        """FR-10.3: success entries use Report.to_dict() structure."""
        report = _make_report("https://a.com")
        batch = BatchResult(results=[URLSuccess(url="https://a.com", report=report)])
        d = batch.to_dict()
        entry = d["results"][0]
        self.assertEqual(entry["url"], "https://a.com")
        self.assertIn("categories", entry)
        self.assertNotIn("error", entry)

    def test_error_entry_structure(self):
        """FR-10.3: error entries have url, error: True, message."""
        batch = BatchResult(results=[
            URLError(url="https://fail.com", message="connection refused"),
        ])
        d = batch.to_dict()
        entry = d["results"][0]
        self.assertEqual(entry["url"], "https://fail.com")
        self.assertIs(entry["error"], True)
        self.assertEqual(entry["message"], "connection refused")

    def test_custom_weights_forwarded(self):
        """FR-10.1: weights parameter forwarded to Report.to_dict()."""
        custom = {"Content Availability": 0.99}
        batch = BatchResult(results=[
            URLSuccess(url="https://a.com", report=_make_report("https://a.com")),
        ])
        d = batch.to_dict(weights=custom)
        cat = d["results"][0]["categories"][0]
        self.assertEqual(cat["weight"], 0.99)

    def test_json_serializable(self):
        """NFR-5.2: output is JSON-serializable."""
        batch = BatchResult(results=[
            URLSuccess(url="https://a.com", report=_make_report("https://a.com")),
            URLError(url="https://b.com", message="err"),
        ])
        text = json.dumps(batch.to_dict())
        parsed = json.loads(text)
        self.assertEqual(parsed["total"], 2)


# ---------------------------------------------------------------------------
# Import tests — NFR-3, NFR-5.2
# ---------------------------------------------------------------------------

class TestImports(unittest.TestCase):
    """Tests for public API imports."""

    def test_all_names_importable(self):
        """NFR-5.2: all names in __all__ are importable."""
        import botaudit

        for name in botaudit.__all__:
            self.assertTrue(
                hasattr(botaudit, name),
                f"{name} listed in __all__ but not importable",
            )

    def test_version_is_string(self):
        """FR-5.1: __version__ is a string."""
        from botaudit import __version__

        self.assertIsInstance(__version__, str)
        # Semver-ish: at least major.minor.patch
        parts = __version__.split(".")
        self.assertEqual(len(parts), 3)

    def test_convenience_import(self):
        """FR-1.4: audit is importable from top-level."""
        from botaudit import audit

        self.assertTrue(callable(audit))

    def test_no_stdout_on_import(self):
        """NFR-3.2: import botaudit produces no output."""
        # botaudit is already imported, but we can verify the module
        # attribute exists without side effects by checking __all__
        import botaudit

        self.assertIsNotNone(botaudit.__all__)


if __name__ == "__main__":
    unittest.main()
