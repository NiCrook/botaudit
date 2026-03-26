"""Tests for batch URL scanning (SPEC-batch)."""

import csv
import io
import json
import os
import tempfile
import unittest

from botaudit.batch import (
    BatchResult,
    URLError,
    URLSuccess,
    collect_urls,
    determine_exit_code,
    format_batch_csv,
    format_batch_json,
    format_batch_text,
    format_summary_table,
    parse_url_file,
    validate_url,
)
from botaudit.models import CategoryResult, Report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(url: str, grade: str = "B", score: float = 85.0) -> Report:
    """Build a minimal Report for testing."""
    return Report(
        url=url,
        categories=[CategoryResult(name="Content Availability", score=score)],
        overall_score=score,
        grade=grade,
    )


def _make_batch(*specs: tuple) -> BatchResult:
    """Build a BatchResult from (url, grade, score) or (url, error_msg) tuples."""
    results = []
    for spec in specs:
        if len(spec) == 3:
            url, grade, score = spec
            results.append(URLSuccess(url=url, report=_make_report(url, grade, score)))
        else:
            url, msg = spec
            results.append(URLError(url=url, message=msg))
    return BatchResult(results=results)


def _write_temp_file(content: str) -> str:
    """Write content to a temp file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".txt")
    os.write(fd, content.encode("utf-8"))
    os.close(fd)
    return path


# ===========================================================================
# FR-2 / NFR-5.1 — URL file parsing (pure functions, no HTTP)
# ===========================================================================

class TestParseUrlFile(unittest.TestCase):
    """FR-2: URL file format parsing."""

    def test_basic_urls(self):
        """FR-2.1: One URL per line."""
        source = io.StringIO("https://a.com\nhttps://b.com\n")
        entries = parse_url_file(source)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], (1, "https://a.com"))
        self.assertEqual(entries[1], (2, "https://b.com"))

    def test_blank_lines_ignored(self):
        """FR-2.2: Empty / whitespace-only lines skipped."""
        source = io.StringIO("https://a.com\n\n   \nhttps://b.com\n")
        entries = parse_url_file(source)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0][1], "https://a.com")
        self.assertEqual(entries[1][1], "https://b.com")

    def test_comments_ignored(self):
        """FR-2.3: Lines starting with '#' are comments."""
        source = io.StringIO("# This is a comment\nhttps://a.com\n  # indented\n")
        entries = parse_url_file(source)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "https://a.com")

    def test_whitespace_stripped(self):
        """FR-2.4: Leading/trailing whitespace stripped."""
        source = io.StringIO("  https://a.com  \n\thttps://b.com\t\n")
        entries = parse_url_file(source)
        self.assertEqual(entries[0][1], "https://a.com")
        self.assertEqual(entries[1][1], "https://b.com")

    def test_inline_comment_not_stripped(self):
        """FR-2.3: Only full-line comments — '#' mid-URL is kept."""
        source = io.StringIO("https://a.com/page#section\n")
        entries = parse_url_file(source)
        self.assertEqual(entries[0][1], "https://a.com/page#section")


class TestValidateUrl(unittest.TestCase):
    """FR-2.5: URL validation rules."""

    def test_valid_http(self):
        self.assertEqual(validate_url("http://example.com"), "http://example.com")

    def test_valid_https(self):
        self.assertEqual(validate_url("https://example.com"), "https://example.com")

    def test_missing_scheme(self):
        self.assertIsNone(validate_url("example.com"))

    def test_ftp_scheme_rejected(self):
        self.assertIsNone(validate_url("ftp://example.com"))

    def test_missing_netloc(self):
        self.assertIsNone(validate_url("https://"))


# ===========================================================================
# FR-3 — Deduplication
# ===========================================================================

class TestCollectUrls(unittest.TestCase):
    """FR-1 / FR-3: URL collection, validation, and deduplication."""

    def test_positional_only(self):
        """FR-1.1: Accept positional URLs."""
        urls = collect_urls(["https://a.com", "https://b.com"])
        self.assertEqual(urls, ["https://a.com", "https://b.com"])

    def test_file_only(self):
        """FR-1.2: Accept --file."""
        path = _write_temp_file("https://a.com\nhttps://b.com\n")
        try:
            urls = collect_urls([], file_path=path)
            self.assertEqual(urls, ["https://a.com", "https://b.com"])
        finally:
            os.unlink(path)

    def test_combined_sources(self):
        """FR-1.4: Positional + file combined."""
        path = _write_temp_file("https://b.com\nhttps://c.com\n")
        try:
            urls = collect_urls(["https://a.com"], file_path=path)
            self.assertEqual(urls, ["https://a.com", "https://b.com", "https://c.com"])
        finally:
            os.unlink(path)

    def test_deduplication_preserves_order(self):
        """FR-3.1: Duplicates removed, first occurrence kept."""
        urls = collect_urls([
            "https://a.com", "https://b.com", "https://a.com", "https://c.com",
        ])
        self.assertEqual(urls, ["https://a.com", "https://b.com", "https://c.com"])

    def test_deduplication_case_sensitive(self):
        """FR-3.2: Case-sensitive comparison."""
        urls = collect_urls(["https://A.com", "https://a.com"])
        self.assertEqual(urls, ["https://A.com", "https://a.com"])

    def test_no_valid_urls_exits(self):
        """FR-2.7: Zero valid URLs after parsing → exit code 2."""
        path = _write_temp_file("not-a-url\nalso-bad\n")
        try:
            with self.assertRaises(SystemExit) as ctx:
                collect_urls([], file_path=path)
            self.assertEqual(ctx.exception.code, 2)
        finally:
            os.unlink(path)


# ===========================================================================
# FR-6 — Text output
# ===========================================================================

class TestFormatBatchText(unittest.TestCase):
    """FR-6: Batch text format."""

    def test_multiple_reports_separated(self):
        """FR-6.1/FR-6.2: Reports separated by blank line + separator."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "B", 85.0),
        )
        text = format_batch_text(batch)
        # Both URLs should appear in the output
        self.assertIn("https://a.com", text)
        self.assertIn("https://b.com", text)
        # Separator between reports
        self.assertIn("=" * 50, text)

    def test_summary_table_present(self):
        """FR-6.3: Summary table after individual reports."""
        batch = _make_batch(("https://a.com", "A", 95.0))
        text = format_batch_text(batch)
        self.assertIn("Batch Summary", text)

    def test_summary_header_has_count(self):
        """FR-6.4: Header line includes URL count."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "B", 85.0),
        )
        text = format_batch_text(batch)
        self.assertIn("Batch Summary (2 URLs)", text)

    def test_failed_url_shows_err(self):
        """FR-6.6: Failed URLs show ERR grade."""
        batch = _make_batch(("https://fail.com", "Timed out"))
        text = format_batch_text(batch)
        self.assertIn("ERR", text)
        self.assertIn("Timed out", text)


class TestFormatSummaryTable(unittest.TestCase):
    """FR-6.3–FR-6.6: Summary table formatting."""

    def test_columns_present(self):
        """FR-6.3: URL, Grade, Score columns."""
        batch = _make_batch(("https://a.com", "A", 95.0))
        table = format_summary_table(batch)
        self.assertIn("URL", table)
        self.assertIn("Grade", table)
        self.assertIn("Score", table)

    def test_row_order_matches_input(self):
        """FR-6.5: Rows in processing order."""
        batch = _make_batch(
            ("https://first.com", "A", 95.0),
            ("https://second.com", "B", 85.0),
        )
        table = format_summary_table(batch)
        first_pos = table.index("https://first.com")
        second_pos = table.index("https://second.com")
        self.assertLess(first_pos, second_pos)

    def test_error_row_format(self):
        """FR-6.6: ERR / — / reason for failed URLs."""
        batch = _make_batch(("https://fail.com", "Connection refused"))
        table = format_summary_table(batch)
        self.assertIn("ERR", table)
        self.assertIn("Connection refused", table)


# ===========================================================================
# FR-7 — JSON output
# ===========================================================================

class TestFormatBatchJson(unittest.TestCase):
    """FR-7: Batch JSON format."""

    def test_top_level_keys(self):
        """FR-7.1: batch, total, succeeded, failed, results."""
        batch = _make_batch(("https://a.com", "A", 95.0))
        data = json.loads(format_batch_json(batch))
        self.assertTrue(data["batch"])
        self.assertIn("total", data)
        self.assertIn("succeeded", data)
        self.assertIn("failed", data)
        self.assertIn("results", data)

    def test_success_object_structure(self):
        """FR-7.3: Matches single-URL JSON."""
        batch = _make_batch(("https://a.com", "A", 95.0))
        data = json.loads(format_batch_json(batch))
        result = data["results"][0]
        self.assertEqual(result["url"], "https://a.com")
        self.assertEqual(result["grade"], "A")
        self.assertEqual(result["overall_score"], 95.0)
        self.assertIn("categories", result)

    def test_error_object_structure(self):
        """FR-7.4: url, error: true, message."""
        batch = _make_batch(("https://fail.com", "Timed out"))
        data = json.loads(format_batch_json(batch))
        result = data["results"][0]
        self.assertEqual(result["url"], "https://fail.com")
        self.assertTrue(result["error"])
        self.assertEqual(result["message"], "Timed out")

    def test_counts_correct(self):
        """FR-7.1: succeeded + failed = total."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://fail.com", "Timed out"),
            ("https://b.com", "B", 85.0),
        )
        data = json.loads(format_batch_json(batch))
        self.assertEqual(data["total"], 3)
        self.assertEqual(data["succeeded"], 2)
        self.assertEqual(data["failed"], 1)
        self.assertEqual(data["succeeded"] + data["failed"], data["total"])


# ===========================================================================
# FR-8 — CSV output
# ===========================================================================

class TestFormatBatchCsv(unittest.TestCase):
    """FR-8: Batch CSV format."""

    def test_single_header_row(self):
        """FR-8.4: Header appears exactly once."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "B", 85.0),
        )
        output = format_batch_csv(batch)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        # First row is header, remaining are data
        self.assertEqual(rows[0][0], "url")
        # No other row should start with "url"
        for row in rows[1:]:
            self.assertNotEqual(row[0], "url")

    def test_success_rows_match_single_url(self):
        """FR-8.2: Success rows identical to single-URL format."""
        batch = _make_batch(("https://a.com", "A", 95.0))
        output = format_batch_csv(batch)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        # Header + 1 category row
        self.assertEqual(len(rows), 2)
        data_row = rows[1]
        self.assertEqual(data_row[0], "https://a.com")  # url
        self.assertEqual(data_row[2], "A")  # grade
        self.assertEqual(data_row[3], "Content Availability")  # category

    def test_error_row_format(self):
        """FR-8.3: Failed URL gets single error row."""
        batch = _make_batch(("https://fail.com", "Connection refused"))
        output = format_batch_csv(batch)
        reader = csv.reader(io.StringIO(output))
        rows = list(reader)
        # Header + 1 error row
        self.assertEqual(len(rows), 2)
        data_row = rows[1]
        self.assertEqual(data_row[0], "https://fail.com")
        self.assertEqual(data_row[2], "ERR")  # grade
        self.assertEqual(data_row[3], "error")  # category
        self.assertIn("Connection refused", data_row[6])  # findings


# ===========================================================================
# FR-9 — Exit codes
# ===========================================================================

class TestDetermineExitCode(unittest.TestCase):
    """FR-9: Exit code behavior."""

    def test_all_success_no_fail_under(self):
        """FR-9.1: 0 when all succeed, no --fail-under."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "B", 85.0),
        )
        self.assertEqual(determine_exit_code(batch), 0)

    def test_all_failed(self):
        """FR-9.2: 1 when all URLs fail."""
        batch = _make_batch(
            ("https://a.com", "Timed out"),
            ("https://b.com", "Connection refused"),
        )
        self.assertEqual(determine_exit_code(batch), 1)

    def test_fail_under_violation(self):
        """FR-9.3: 1 when any grade below threshold."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "C", 75.0),
        )
        self.assertEqual(determine_exit_code(batch, fail_under="B"), 1)

    def test_failed_urls_not_evaluated(self):
        """FR-9.4: Failed URLs ignored for --fail-under."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://fail.com", "Timed out"),
        )
        # Should be 0 — the failed URL is ignored, and A >= B
        self.assertEqual(determine_exit_code(batch, fail_under="B"), 0)

    def test_all_failed_with_fail_under(self):
        """FR-9.5: 1 when --fail-under set and all fail."""
        batch = _make_batch(
            ("https://a.com", "Timed out"),
            ("https://b.com", "Connection refused"),
        )
        self.assertEqual(determine_exit_code(batch, fail_under="B"), 1)

    def test_mixed_results_no_fail_under(self):
        """FR-9.1/FR-5.5: 0 when some succeed, some fail, no --fail-under."""
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://fail.com", "Timed out"),
        )
        self.assertEqual(determine_exit_code(batch), 0)


# ===========================================================================
# BatchResult properties
# ===========================================================================

class TestBatchResult(unittest.TestCase):
    """BatchResult aggregate properties."""

    def test_total_count(self):
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "Timed out"),
        )
        self.assertEqual(batch.total, 2)

    def test_succeeded_count(self):
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "Timed out"),
            ("https://c.com", "B", 85.0),
        )
        self.assertEqual(batch.succeeded, 2)

    def test_failed_count(self):
        batch = _make_batch(
            ("https://a.com", "A", 95.0),
            ("https://b.com", "Timed out"),
        )
        self.assertEqual(batch.failed, 1)

    def test_empty_batch(self):
        batch = BatchResult()
        self.assertEqual(batch.total, 0)
        self.assertEqual(batch.succeeded, 0)
        self.assertEqual(batch.failed, 0)


if __name__ == "__main__":
    unittest.main()
