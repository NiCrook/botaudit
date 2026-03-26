"""Tests for configuration file support (SPEC-config)."""

import argparse
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from botaudit.config import (
    _discover,
    _validate,
    load_config,
    load_config_for_cli,
    merge_config_into_args,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(directory: Path, name: str, content: str) -> Path:
    """Write a file inside *directory* and return its path."""
    p = directory / name
    p.write_text(textwrap.dedent(content))
    return p


def _write_yaml(directory: Path, content: str) -> Path:
    return _write(directory, ".botaudit.yaml", content)


def _write_toml(directory: Path, content: str) -> Path:
    return _write(directory, "pyproject.toml", content)


def _make_args(**overrides) -> argparse.Namespace:
    """Build a minimal argparse Namespace with CLI defaults."""
    defaults = dict(
        output_format="text",
        timeout=10.0,
        fail_under=None,
        quiet=False,
        no_recommendations=False,
        skip_llm_discovery=False,
        weight_profile=None,
        weight_overrides=None,
        page_type=None,
        no_page_type=False,
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ---------------------------------------------------------------------------
# Discovery tests — FR-1
# ---------------------------------------------------------------------------

class TestDiscovery(unittest.TestCase):
    """Tests for config file discovery."""

    def test_yaml_found(self):
        """FR-1.1: .botaudit.yaml is discovered."""
        with tempfile.TemporaryDirectory() as d:
            _write_yaml(Path(d), "format: json\n")
            result = _discover(Path(d))
            self.assertIsNotNone(result)
            data, source = result
            self.assertEqual(data["format"], "json")
            self.assertIn(".botaudit.yaml", source)

    def test_toml_found(self):
        """FR-1.1: [tool.botaudit] in pyproject.toml is discovered."""
        with tempfile.TemporaryDirectory() as d:
            _write_toml(Path(d), """\
                [tool.botaudit]
                format = "csv"
            """)
            result = _discover(Path(d))
            self.assertIsNotNone(result)
            data, source = result
            self.assertEqual(data["format"], "csv")
            self.assertIn("pyproject.toml", source)

    def test_both_present_error(self):
        """FR-1.3: both .botaudit.yaml and [tool.botaudit] → error."""
        with tempfile.TemporaryDirectory() as d:
            _write_yaml(Path(d), "format: json\n")
            _write_toml(Path(d), """\
                [tool.botaudit]
                format = "csv"
            """)
            with self.assertRaises(ValueError) as ctx:
                _discover(Path(d))
            self.assertIn("both", str(ctx.exception).lower())

    def test_neither_present(self):
        """FR-1.4: no config file → returns None, no error."""
        with tempfile.TemporaryDirectory() as d:
            result = _discover(Path(d))
            self.assertIsNone(result)

    def test_toml_without_tool_botaudit(self):
        """pyproject.toml without [tool.botaudit] → None."""
        with tempfile.TemporaryDirectory() as d:
            _write_toml(Path(d), """\
                [project]
                name = "something"
            """)
            result = _discover(Path(d))
            self.assertIsNone(result)

    def test_empty_yaml(self):
        """Empty .botaudit.yaml → empty dict."""
        with tempfile.TemporaryDirectory() as d:
            _write_yaml(Path(d), "")
            result = _discover(Path(d))
            self.assertIsNotNone(result)
            data, _ = result
            self.assertEqual(data, {})


# ---------------------------------------------------------------------------
# Parsing tests — FR-2, FR-4, FR-5
# ---------------------------------------------------------------------------

class TestParsing(unittest.TestCase):
    """Tests for YAML and TOML parsing."""

    def test_all_keys_yaml(self):
        """FR-2.1: all recognized keys accepted in YAML."""
        with tempfile.TemporaryDirectory() as d:
            _write_yaml(Path(d), """\
                format: json
                timeout: 15.0
                fail_under: B
                quiet: true
                no_recommendations: true
                skip_llm_discovery: true
                weight_profile: ecommerce
                weights:
                  llm: 0.20
                page_type: auto
                no_page_type: false
            """)
            config = load_config(str(Path(d) / ".botaudit.yaml"))
            self.assertEqual(config["format"], "json")
            self.assertEqual(config["timeout"], 15.0)
            self.assertEqual(config["fail_under"], "B")
            self.assertIs(config["quiet"], True)
            self.assertEqual(config["weight_profile"], "ecommerce")
            self.assertEqual(config["weights"]["llm"], 0.20)

    def test_all_keys_toml(self):
        """FR-2.1: all recognized keys accepted in TOML."""
        with tempfile.TemporaryDirectory() as d:
            _write_toml(Path(d), """\
                [tool.botaudit]
                format = "json"
                timeout = 15.0
                fail_under = "B"
                quiet = true
                no_recommendations = true
                skip_llm_discovery = true
                weight_profile = "ecommerce"
                page_type = "auto"
                no_page_type = false

                [tool.botaudit.weights]
                llm = 0.20
            """)
            config = load_config(str(Path(d) / "pyproject.toml"))
            self.assertEqual(config["format"], "json")
            self.assertEqual(config["timeout"], 15.0)

    def test_weights_percentage_string(self):
        """FR-2.3: percentage strings in weights are accepted."""
        data = {"weights": {"llm": "30%"}}
        result = _validate(data, "test")
        self.assertEqual(result["weights"]["llm"], "30%")

    def test_weights_aliases(self):
        """FR-2.3: category aliases are accepted in weights."""
        data = {"weights": {"structured-data": 0.25, "content": 0.30}}
        result = _validate(data, "test")
        # Should not raise
        self.assertIn("structured-data", result["weights"])

    def test_yaml_syntax_error(self):
        """YAML syntax error → ValueError."""
        with tempfile.TemporaryDirectory() as d:
            _write_yaml(Path(d), "format: [invalid yaml\n")
            with self.assertRaises(Exception):
                load_config(str(Path(d) / ".botaudit.yaml"))

    def test_toml_syntax_error(self):
        """TOML syntax error → ValueError via tomllib."""
        with tempfile.TemporaryDirectory() as d:
            _write_toml(Path(d), "not valid toml [[[")
            with self.assertRaises(Exception):
                load_config(str(Path(d) / "pyproject.toml"))


# ---------------------------------------------------------------------------
# Validation tests — FR-6
# ---------------------------------------------------------------------------

class TestValidation(unittest.TestCase):
    """Tests for config validation."""

    def test_unknown_key(self):
        """FR-2.2: unrecognized key → error naming the key."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"bogus_key": True}, "test.yaml")
        self.assertIn("bogus_key", str(ctx.exception))

    def test_invalid_format(self):
        """Invalid format value → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"format": "xml"}, "test.yaml")
        self.assertIn("format", str(ctx.exception))

    def test_invalid_fail_under(self):
        """Invalid fail_under → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"fail_under": "Z"}, "test.yaml")
        self.assertIn("fail_under", str(ctx.exception))

    def test_negative_timeout(self):
        """Negative timeout → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"timeout": -1.0}, "test.yaml")
        self.assertIn("timeout", str(ctx.exception))

    def test_unknown_weight_profile(self):
        """Unknown weight_profile → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"weight_profile": "nonexistent"}, "test.yaml")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_unknown_category_in_weights(self):
        """Unknown category in weights → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"weights": {"fake_cat": 0.5}}, "test.yaml")
        self.assertIn("fake_cat", str(ctx.exception))

    def test_negative_weight(self):
        """Negative weight value → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"weights": {"llm": -0.5}}, "test.yaml")
        self.assertIn("non-negative", str(ctx.exception))

    def test_mutual_exclusion(self):
        """no_page_type + page_type → mutual exclusion error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"no_page_type": True, "page_type": "article"}, "test.yaml")
        self.assertIn("mutually exclusive", str(ctx.exception))

    def test_unknown_page_type(self):
        """Unknown page_type → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"page_type": "spaceship"}, "test.yaml")
        self.assertIn("spaceship", str(ctx.exception))

    def test_wrong_type(self):
        """Wrong type for a key → error."""
        with self.assertRaises(ValueError) as ctx:
            _validate({"quiet": "yes"}, "test.yaml")
        self.assertIn("bool", str(ctx.exception))

    def test_valid_config_passes(self):
        """A fully valid config passes without errors."""
        config = {
            "format": "json",
            "timeout": 5.0,
            "fail_under": "C",
            "quiet": True,
            "weight_profile": "docs",
            "weights": {"llm": 0.25},
        }
        result = _validate(config, "test.yaml")
        self.assertEqual(result, config)


# ---------------------------------------------------------------------------
# Precedence tests — FR-3
# ---------------------------------------------------------------------------

class TestPrecedence(unittest.TestCase):
    """Tests for CLI-over-config precedence."""

    def test_cli_format_overrides_config(self):
        """FR-3.1: CLI --format overrides config format."""
        args = _make_args(output_format="json")
        config = {"format": "csv"}
        merge_config_into_args(args, config, explicit_flags={"output_format"})
        self.assertEqual(args.output_format, "json")

    def test_config_applied_when_no_cli(self):
        """FR-3.2: config value applied when CLI not explicit."""
        args = _make_args()
        config = {"format": "html", "timeout": 30.0, "quiet": True}
        merge_config_into_args(args, config, explicit_flags=set())
        self.assertEqual(args.output_format, "html")
        self.assertEqual(args.timeout, 30.0)
        self.assertIs(args.quiet, True)

    def test_config_bool_not_overridden_by_argparse_default(self):
        """FR-3.5: config quiet=true not overridden by argparse default false."""
        args = _make_args(quiet=False)  # argparse default
        config = {"quiet": True}
        # quiet NOT in explicit_flags because user didn't pass --quiet
        merge_config_into_args(args, config, explicit_flags=set())
        self.assertIs(args.quiet, True)

    def test_cli_bool_overrides_config(self):
        """FR-3.5: explicit --quiet false-ish (not passed) vs config."""
        args = _make_args(quiet=False)
        config = {"quiet": True}
        # User explicitly passed --quiet (or didn't, but the flag is tracked)
        # Actually test: if user passed --no-recommendations, that flag wins
        args2 = _make_args(no_recommendations=True)
        config2 = {"no_recommendations": False}
        merge_config_into_args(args2, config2, explicit_flags={"no_recommendations"})
        self.assertIs(args2.no_recommendations, True)

    def test_cli_weight_overrides_config_category(self):
        """FR-3.3: CLI --weight overrides individual category from config."""
        args = _make_args(weight_overrides=["LLM Discoverability=0.15"])
        config = {"weights": {"content": 0.30, "llm": 0.20}}
        merge_config_into_args(args, config, explicit_flags={"weight_overrides"})
        # Config weights come first, then CLI overrides (last wins)
        self.assertIsNotNone(args.weight_overrides)
        # The last entry for LLM should be the CLI one
        llm_entries = [e for e in args.weight_overrides if "LLM" in e]
        self.assertTrue(llm_entries[-1].endswith("0.15"))

    def test_config_weights_when_no_cli_weight(self):
        """Config weights applied when no CLI --weight flags."""
        args = _make_args(weight_overrides=None)
        config = {"weights": {"llm": 0.20}}
        merge_config_into_args(args, config, explicit_flags=set())
        self.assertIsNotNone(args.weight_overrides)
        self.assertEqual(len(args.weight_overrides), 1)

    def test_cli_weight_profile_overrides_config(self):
        """FR-3.4: CLI --weight-profile replaces config weight_profile."""
        args = _make_args(weight_profile="docs")
        config = {"weight_profile": "ecommerce"}
        merge_config_into_args(args, config, explicit_flags={"weight_profile"})
        self.assertEqual(args.weight_profile, "docs")


# ---------------------------------------------------------------------------
# load_config() library API tests — FR-7
# ---------------------------------------------------------------------------

class TestLoadConfig(unittest.TestCase):
    """Tests for the public load_config() function."""

    def test_explicit_path_yaml(self):
        """FR-7.2: load_config(path) loads from explicit YAML path."""
        with tempfile.TemporaryDirectory() as d:
            p = _write_yaml(Path(d), "format: json\ntimeout: 5.0\n")
            config = load_config(str(p))
            self.assertEqual(config["format"], "json")
            self.assertEqual(config["timeout"], 5.0)

    def test_explicit_path_not_found(self):
        """FR-7.2: load_config raises FileNotFoundError for missing path."""
        with self.assertRaises(FileNotFoundError):
            load_config("/no/such/file.yaml")

    def test_invalid_content_raises_value_error(self):
        """FR-7.2: invalid config content raises ValueError."""
        with tempfile.TemporaryDirectory() as d:
            p = _write_yaml(Path(d), "bogus_key: true\n")
            with self.assertRaises(ValueError):
                load_config(str(p))

    def test_auto_discovery(self):
        """FR-7.2: load_config(None) uses auto-discovery from cwd."""
        with tempfile.TemporaryDirectory() as d:
            _write_yaml(Path(d), "format: csv\n")
            with patch("botaudit.config.Path") as mock_path:
                mock_path.cwd.return_value = Path(d)
                mock_path.side_effect = Path
                config = load_config(None)
            self.assertEqual(config["format"], "csv")

    def test_auto_discovery_no_file(self):
        """FR-7.2: load_config(None) returns empty dict when no file found."""
        with tempfile.TemporaryDirectory() as d:
            with patch("botaudit.config.Path") as mock_path:
                mock_path.cwd.return_value = Path(d)
                mock_path.side_effect = Path
                config = load_config(None)
            self.assertEqual(config, {})


# ---------------------------------------------------------------------------
# load_config_for_cli() tests — FR-1.5, FR-1.6, FR-6.3
# ---------------------------------------------------------------------------

class TestLoadConfigForCli(unittest.TestCase):
    """Tests for CLI config loading."""

    def test_config_none_disables_loading(self):
        """FR-1.6: --config none returns empty dict."""
        config = load_config_for_cli("none")
        self.assertEqual(config, {})

    def test_config_none_case_insensitive(self):
        """FR-1.6: --config None (mixed case) also works."""
        config = load_config_for_cli("None")
        self.assertEqual(config, {})

    def test_explicit_path(self):
        """FR-1.5: --config path/to/file.yaml loads that file."""
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), "custom.yaml", "format: html\n")
            config = load_config_for_cli(str(p))
            self.assertEqual(config["format"], "html")

    def test_invalid_file_exits_2(self):
        """FR-6.3: validation error → sys.exit(2)."""
        with tempfile.TemporaryDirectory() as d:
            p = _write(Path(d), "bad.yaml", "unknown_key: true\n")
            with self.assertRaises(SystemExit) as ctx:
                load_config_for_cli(str(p))
            self.assertEqual(ctx.exception.code, 2)

    def test_missing_file_exits_2(self):
        """FR-6.3: missing explicit file → sys.exit(2)."""
        with self.assertRaises(SystemExit) as ctx:
            load_config_for_cli("/no/such/file.yaml")
        self.assertEqual(ctx.exception.code, 2)

    def test_auto_discover_from_cwd(self):
        """Auto-discovery from specified cwd."""
        with tempfile.TemporaryDirectory() as d:
            _write_yaml(Path(d), "timeout: 20.0\n")
            config = load_config_for_cli(None, cwd=Path(d))
            self.assertEqual(config["timeout"], 20.0)

    def test_auto_discover_no_file(self):
        """No config file in cwd → empty dict."""
        with tempfile.TemporaryDirectory() as d:
            config = load_config_for_cli(None, cwd=Path(d))
            self.assertEqual(config, {})


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestCliIntegration(unittest.TestCase):
    """End-to-end tests for config integration with the CLI parser."""

    def test_config_flag_in_parser(self):
        """--config flag is present in the parser."""
        from botaudit.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["--config", "none", "https://example.com"])
        self.assertEqual(args.config, "none")

    def test_detect_explicit_flags(self):
        """_detect_explicit_flags identifies which flags were passed."""
        from botaudit.cli import _detect_explicit_flags, build_parser
        parser = build_parser()
        explicit = _detect_explicit_flags(parser, ["--format", "json", "--quiet"])
        self.assertIn("output_format", explicit)
        self.assertIn("quiet", explicit)
        self.assertNotIn("timeout", explicit)

    def test_detect_explicit_short_flags(self):
        """Short flags like -q are detected."""
        from botaudit.cli import _detect_explicit_flags, build_parser
        parser = build_parser()
        explicit = _detect_explicit_flags(parser, ["-q", "-w", "llm=0.5"])
        self.assertIn("quiet", explicit)
        self.assertIn("weight_overrides", explicit)


if __name__ == "__main__":
    unittest.main()
