"""Tests for --fail-under flag."""

import unittest

from botaudit.models import GRADE_THRESHOLDS

# Grade ordering used by --fail-under
GRADE_ORDER = {letter: score for score, letter in GRADE_THRESHOLDS}


class TestFailUnderLogic(unittest.TestCase):

    def test_grade_order_values(self):
        self.assertEqual(GRADE_ORDER["A"], 90)
        self.assertEqual(GRADE_ORDER["B"], 80)
        self.assertEqual(GRADE_ORDER["C"], 70)
        self.assertEqual(GRADE_ORDER["D"], 60)
        self.assertEqual(GRADE_ORDER["F"], 0)

    def test_same_grade_passes(self):
        """Grade B with --fail-under B should pass."""
        self.assertGreaterEqual(GRADE_ORDER["B"], GRADE_ORDER["B"])

    def test_higher_grade_passes(self):
        """Grade A with --fail-under B should pass."""
        self.assertGreaterEqual(GRADE_ORDER["A"], GRADE_ORDER["B"])

    def test_lower_grade_fails(self):
        """Grade C with --fail-under B should fail."""
        self.assertLess(GRADE_ORDER["C"], GRADE_ORDER["B"])

    def test_f_fails_under_any(self):
        for grade in ["A", "B", "C", "D"]:
            self.assertLess(GRADE_ORDER["F"], GRADE_ORDER[grade])

    def test_a_passes_all(self):
        for grade in ["A", "B", "C", "D", "F"]:
            self.assertGreaterEqual(GRADE_ORDER["A"], GRADE_ORDER[grade])
