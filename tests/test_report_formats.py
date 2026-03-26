"""Tests for JSON and CSV output formats."""

import csv
import io
import json
import unittest

from botaudit.models import CategoryResult, Recommendation, Report, Severity
from botaudit.report import format_csv, format_json, format_report


def _make_report():
    return Report(
        url="https://example.com",
        overall_score=82.0,
        grade="B",
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


class TestFormatJson(unittest.TestCase):

    def test_valid_json(self):
        report = _make_report()
        result = format_json(report)
        data = json.loads(result)
        self.assertEqual(data["url"], "https://example.com")
        self.assertEqual(data["grade"], "B")
        self.assertEqual(data["overall_score"], 82.0)
        self.assertEqual(len(data["categories"]), 2)

    def test_categories_have_expected_fields(self):
        data = json.loads(format_json(_make_report()))
        cat = data["categories"][0]
        self.assertIn("name", cat)
        self.assertIn("score", cat)
        self.assertIn("weight", cat)
        self.assertIn("findings", cat)

    def test_recommendations_included(self):
        data = json.loads(format_json(_make_report()))
        cat = data["categories"][1]
        self.assertIn("recommendations", cat)
        self.assertEqual(len(cat["recommendations"]), 1)
        self.assertEqual(cat["recommendations"][0]["severity"], "high")

    def test_recommendations_suppressed(self):
        data = json.loads(format_json(_make_report(), show_recommendations=False))
        for cat in data["categories"]:
            self.assertNotIn("recommendations", cat)


class TestFormatCsv(unittest.TestCase):

    def test_valid_csv(self):
        result = format_csv(_make_report())
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        self.assertEqual(len(rows), 3)  # header + 2 categories

    def test_header_row(self):
        result = format_csv(_make_report())
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        self.assertIn("url", header)
        self.assertIn("category", header)
        self.assertIn("score", header)
        self.assertIn("recommendations", header)

    def test_no_recommendations_column_when_suppressed(self):
        result = format_csv(_make_report(), show_recommendations=False)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        self.assertNotIn("recommendations", header)

    def test_data_rows(self):
        result = format_csv(_make_report())
        reader = csv.reader(io.StringIO(result))
        next(reader)  # skip header
        row = next(reader)
        self.assertEqual(row[0], "https://example.com")
        self.assertEqual(row[4], "Content Availability")
