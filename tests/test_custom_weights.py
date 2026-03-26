"""Tests for custom weight profiles (SPEC-custom-weights)."""

import unittest

from botaudit.models import (
    CATEGORY_WEIGHTS,
    WEIGHT_PROFILES,
    CategoryResult,
    Report,
    format_profiles,
    resolve_weights,
)


class TestResolveWeightsDefaults(unittest.TestCase):
    """resolve_weights returns defaults when no profile or overrides given."""

    def test_returns_default_weights(self):
        result = resolve_weights()
        self.assertEqual(result, CATEGORY_WEIGHTS)

    def test_returns_copy(self):
        result = resolve_weights()
        self.assertIsNot(result, CATEGORY_WEIGHTS)


class TestResolveWeightsProfiles(unittest.TestCase):
    """--weight-profile selects a named preset."""

    def test_each_builtin_profile(self):
        for name, (_, expected) in WEIGHT_PROFILES.items():
            result = resolve_weights(profile=name)
            self.assertEqual(result, expected, f"profile={name}")

    def test_case_insensitive(self):
        self.assertEqual(
            resolve_weights(profile="ECOMMERCE"),
            resolve_weights(profile="ecommerce"),
        )

    def test_unknown_profile_raises(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_weights(profile="nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))
        self.assertIn("Available profiles", str(ctx.exception))


class TestResolveWeightsOverrides(unittest.TestCase):
    """--weight overrides individual category weights."""

    def test_decimal_override(self):
        result = resolve_weights(overrides=["Structured Data=0.50"])
        self.assertAlmostEqual(result["Structured Data"], 0.50)
        # Others unchanged
        self.assertAlmostEqual(result["Semantic HTML"], CATEGORY_WEIGHTS["Semantic HTML"])

    def test_percentage_override(self):
        result = resolve_weights(overrides=["Structured Data=50%"])
        self.assertAlmostEqual(result["Structured Data"], 0.50)

    def test_decimal_and_percentage_equivalent(self):
        a = resolve_weights(overrides=["Structured Data=0.30"])
        b = resolve_weights(overrides=["Structured Data=30%"])
        self.assertEqual(a, b)

    def test_alias_short(self):
        result = resolve_weights(overrides=["structured=0.40"])
        self.assertAlmostEqual(result["Structured Data"], 0.40)

    def test_alias_hyphenated(self):
        result = resolve_weights(overrides=["link-discoverability=0.25"])
        self.assertAlmostEqual(result["Link Discoverability"], 0.25)

    def test_alias_case_insensitive(self):
        result = resolve_weights(overrides=["LLM=0.50"])
        self.assertAlmostEqual(result["LLM Discoverability"], 0.50)

    def test_multiple_overrides(self):
        result = resolve_weights(overrides=[
            "content=0.10",
            "semantic=0.50",
        ])
        self.assertAlmostEqual(result["Content Availability"], 0.10)
        self.assertAlmostEqual(result["Semantic HTML"], 0.50)

    def test_duplicate_last_wins(self):
        result = resolve_weights(overrides=[
            "llm=0.10",
            "llm=0.99",
        ])
        self.assertAlmostEqual(result["LLM Discoverability"], 0.99)

    def test_zero_weight_allowed(self):
        result = resolve_weights(overrides=["llm=0"])
        self.assertAlmostEqual(result["LLM Discoverability"], 0.0)

    def test_unknown_category_raises(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_weights(overrides=["FakeCategory=0.5"])
        self.assertIn("FakeCategory", str(ctx.exception))
        self.assertIn("Valid categories", str(ctx.exception))

    def test_invalid_value_raises(self):
        with self.assertRaises(ValueError):
            resolve_weights(overrides=["llm=abc"])

    def test_negative_value_raises(self):
        with self.assertRaises(ValueError):
            resolve_weights(overrides=["llm=-0.5"])

    def test_missing_equals_raises(self):
        with self.assertRaises(ValueError):
            resolve_weights(overrides=["llm"])

    def test_all_zero_raises(self):
        overrides = [f"{name}=0" for name in CATEGORY_WEIGHTS]
        with self.assertRaises(ValueError) as ctx:
            resolve_weights(overrides=overrides)
        self.assertIn("zero", str(ctx.exception))


class TestResolveWeightsProfilePlusOverride(unittest.TestCase):
    """--weight-profile combined with --weight."""

    def test_override_on_top_of_profile(self):
        result = resolve_weights(
            profile="ecommerce",
            overrides=["LLM Discoverability=0.50"],
        )
        # Override applied
        self.assertAlmostEqual(result["LLM Discoverability"], 0.50)
        # Rest from ecommerce profile
        self.assertAlmostEqual(result["Structured Data"], 0.25)


class TestFormatProfiles(unittest.TestCase):
    """--list-profiles output."""

    def test_contains_all_profile_names(self):
        output = format_profiles()
        for name in WEIGHT_PROFILES:
            self.assertIn(name, output)

    def test_contains_percentages(self):
        output = format_profiles()
        self.assertIn("27%", output)  # default Content Availability


class TestComputeGradeWithWeights(unittest.TestCase):
    """Report.compute_grade honours custom weights."""

    def _make_report(self):
        return Report(
            url="https://example.com",
            categories=[
                CategoryResult(name="Content Availability", score=100.0),
                CategoryResult(name="Semantic HTML", score=0.0),
            ],
        )

    def test_default_weights(self):
        r = self._make_report()
        r.compute_grade()
        # (100*0.27 + 0*0.23) / (0.27+0.23) = 54.0
        self.assertAlmostEqual(r.overall_score, 54.0)

    def test_custom_weights_shift_score(self):
        r = self._make_report()
        r.compute_grade(weights={
            "Content Availability": 0.90,
            "Semantic HTML": 0.10,
        })
        # (100*0.90 + 0*0.10) / 1.0 = 90.0
        self.assertAlmostEqual(r.overall_score, 90.0)
        self.assertEqual(r.grade, "A")

    def test_zero_weight_excludes_category(self):
        r = self._make_report()
        r.compute_grade(weights={
            "Content Availability": 1.0,
            "Semantic HTML": 0.0,
        })
        # Only Content Availability counts → 100
        self.assertAlmostEqual(r.overall_score, 100.0)


class TestCLIWeightFlags(unittest.TestCase):
    """CLI integration: parser accepts weight flags, --list-profiles exits."""

    def test_list_profiles_returns_normally(self):
        from botaudit.cli import main
        # --list-profiles prints and returns (no SystemExit)
        main(["--list-profiles"])  # should not raise

    def test_bad_profile_exits_two(self):
        from botaudit.cli import main
        with self.assertRaises(SystemExit) as ctx:
            main(["--weight-profile", "nope", "https://example.com"])
        self.assertEqual(ctx.exception.code, 2)

    def test_bad_weight_exits_two(self):
        from botaudit.cli import main
        with self.assertRaises(SystemExit) as ctx:
            main(["-w", "fake=1", "https://example.com"])
        self.assertEqual(ctx.exception.code, 2)


class TestSkipLlmWithCustomWeights(unittest.TestCase):
    """--skip-llm-discovery + custom LLM weight doesn't break anything."""

    def test_resolve_weights_still_includes_llm_key(self):
        result = resolve_weights(overrides=["llm=0.50"])
        self.assertIn("LLM Discoverability", result)

    def test_compute_grade_without_llm_category(self):
        """When LLM category is absent, its weight is just unused."""
        r = Report(
            url="https://example.com",
            categories=[
                CategoryResult(name="Content Availability", score=80.0),
            ],
        )
        weights = resolve_weights(overrides=["llm=0.50"])
        r.compute_grade(weights=weights)
        # Only Content Availability present → score = 80
        self.assertAlmostEqual(r.overall_score, 80.0)


if __name__ == "__main__":
    unittest.main()
