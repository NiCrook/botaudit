"""Configuration file discovery, parsing, and validation (SPEC-config).

FR-1: Discover .botaudit.yaml or [tool.botaudit] in pyproject.toml.
FR-2: Validate all recognized keys.
FR-3: Merge with CLI flags (CLI wins).
FR-7: Expose load_config() for library callers.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from botaudit.models import CATEGORY_ALIASES, CATEGORY_WEIGHTS, WEIGHT_PROFILES
from botaudit.page_type import PAGE_TYPES

# FR-2.1: recognized configuration keys and their expected types.
_VALID_KEYS: dict[str, type | tuple[type, ...]] = {
    "format": str,
    "timeout": (int, float),
    "fail_under": str,
    "quiet": bool,
    "no_recommendations": bool,
    "skip_llm_discovery": bool,
    "weight_profile": str,
    "weights": dict,
    "page_type": str,
    "no_page_type": bool,
}

_VALID_FORMATS = {"text", "json", "csv", "html"}
_VALID_GRADES = {"A", "B", "C", "D", "F"}


def _resolve_category(name: str) -> str:
    """Resolve a category name or alias to its canonical form.

    Raises ValueError for unrecognized names.
    """
    key = name.lower()
    # Direct match on canonical names
    lookup = {k.lower(): k for k in CATEGORY_WEIGHTS}
    if key in lookup:
        return lookup[key]
    # Alias match
    alias_lower = {k.lower(): v for k, v in CATEGORY_ALIASES.items()}
    if key in alias_lower:
        return alias_lower[key]
    valid = ", ".join(sorted(CATEGORY_WEIGHTS))
    raise ValueError(f"Unknown category '{name}'. Valid categories: {valid}")


def _validate(config: dict, source_path: str) -> dict:
    """Validate a parsed config dict. Returns the validated dict.

    FR-2.2: unknown keys → error.
    FR-6.1–FR-6.4: type/value validation with descriptive messages.
    """
    errors: list[str] = []

    # FR-2.2: reject unknown keys
    unknown = set(config) - set(_VALID_KEYS)
    if unknown:
        for key in sorted(unknown):
            errors.append(f"unrecognized key '{key}'")

    # Type checks
    for key, expected in _VALID_KEYS.items():
        if key not in config:
            continue
        val = config[key]
        if not isinstance(val, expected):
            expected_name = (
                expected.__name__
                if isinstance(expected, type)
                else " or ".join(t.__name__ for t in expected)
            )
            errors.append(f"'{key}' must be {expected_name}, got {type(val).__name__}")

    # Value validation (only if type is correct)
    if "format" in config and isinstance(config["format"], str):
        if config["format"] not in _VALID_FORMATS:
            errors.append(
                f"'format' must be one of {sorted(_VALID_FORMATS)}, "
                f"got '{config['format']}'"
            )

    if "fail_under" in config and isinstance(config["fail_under"], str):
        if config["fail_under"] not in _VALID_GRADES:
            errors.append(
                f"'fail_under' must be one of {sorted(_VALID_GRADES)}, "
                f"got '{config['fail_under']}'"
            )

    if "timeout" in config and isinstance(config["timeout"], (int, float)):
        if config["timeout"] <= 0:
            errors.append(f"'timeout' must be positive, got {config['timeout']}")

    if "weight_profile" in config and isinstance(config["weight_profile"], str):
        if config["weight_profile"].lower() not in WEIGHT_PROFILES:
            names = ", ".join(sorted(WEIGHT_PROFILES))
            errors.append(
                f"unknown weight profile '{config['weight_profile']}'. "
                f"Available: {names}"
            )

    if "page_type" in config and isinstance(config["page_type"], str):
        val = config["page_type"].lower()
        if val != "auto" and val not in PAGE_TYPES:
            valid = ", ".join(sorted(PAGE_TYPES))
            errors.append(
                f"unknown page type '{config['page_type']}'. "
                f"Valid types: auto, {valid}"
            )

    # FR-6.2: mutual exclusion
    if config.get("no_page_type") is True and "page_type" in config:
        errors.append("'no_page_type' and 'page_type' are mutually exclusive")

    # FR-2.3: validate weights mapping
    if "weights" in config and isinstance(config["weights"], dict):
        for cat_name, cat_val in config["weights"].items():
            try:
                _resolve_category(cat_name)
            except ValueError:
                valid = ", ".join(sorted(CATEGORY_WEIGHTS))
                errors.append(
                    f"unknown category '{cat_name}' in 'weights'. "
                    f"Valid categories: {valid}"
                )
                continue

            # Accept string percentages ("30%") and numeric values
            if isinstance(cat_val, str):
                if cat_val.endswith("%"):
                    try:
                        parsed = float(cat_val[:-1]) / 100.0
                    except ValueError:
                        errors.append(
                            f"invalid weight value '{cat_val}' for '{cat_name}'"
                        )
                        continue
                else:
                    try:
                        parsed = float(cat_val)
                    except ValueError:
                        errors.append(
                            f"invalid weight value '{cat_val}' for '{cat_name}'"
                        )
                        continue
            elif isinstance(cat_val, (int, float)):
                parsed = float(cat_val)
            else:
                errors.append(
                    f"weight for '{cat_name}' must be a number or percentage string, "
                    f"got {type(cat_val).__name__}"
                )
                continue

            if parsed < 0:
                errors.append(
                    f"weight for '{cat_name}' must be non-negative, got {parsed}"
                )

    if errors:
        detail = "; ".join(errors)
        raise ValueError(f"{source_path}: {detail}")

    return config


def _parse_weights(raw: dict) -> list[str]:
    """Convert a weights mapping to CLI-compatible 'CATEGORY=VALUE' strings.

    Resolves aliases to canonical names and normalizes percentage strings.
    """
    result: list[str] = []
    for name, val in raw.items():
        canonical = _resolve_category(name)
        if isinstance(val, str) and val.endswith("%"):
            numeric = float(val[:-1]) / 100.0
        else:
            numeric = float(val)
        result.append(f"{canonical}={numeric}")
    return result


def _discover(cwd: Path) -> tuple[dict, str] | None:
    """FR-1.2/FR-1.3: Discover config file in *cwd*.

    Returns (parsed_dict, source_path) or None if no config found.
    Raises ValueError if both sources exist (FR-1.3).
    """
    yaml_path = cwd / ".botaudit.yaml"
    toml_path = cwd / "pyproject.toml"

    has_yaml = yaml_path.is_file()
    has_toml = False
    toml_config: dict | None = None

    if toml_path.is_file():
        with open(toml_path, "rb") as f:
            toml_data = tomllib.load(f)
        if "tool" in toml_data and "botaudit" in toml_data["tool"]:
            has_toml = True
            toml_config = toml_data["tool"]["botaudit"]

    # FR-1.3: both present is an error
    if has_yaml and has_toml:
        raise ValueError(
            f"Found both '{yaml_path}' and [tool.botaudit] in '{toml_path}'. "
            f"Remove one to avoid ambiguity."
        )

    if has_yaml:
        try:
            import yaml
        except ImportError:
            raise ValueError(
                f"Found '{yaml_path}' but pyyaml is not installed. "
                f"Install it with: pip install pyyaml — or use "
                f"[tool.botaudit] in pyproject.toml instead."
            )
        with open(yaml_path) as f:
            # NFR-4.1: safe_load only
            data = yaml.safe_load(f)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"{yaml_path}: expected a YAML mapping at top level")
        return data, str(yaml_path)

    if has_toml and toml_config is not None:
        return dict(toml_config), f"{toml_path} [tool.botaudit]"

    # FR-1.4: no config found
    return None


def load_config(
    path: str | None = None,
) -> dict[str, object]:
    """Load and validate a botaudit configuration file.

    FR-7.2: Library-facing entry point.

    When *path* is None, uses automatic discovery (FR-1.2).
    Returns a dict of validated configuration values.
    Raises FileNotFoundError when *path* is given but does not exist.
    Raises ValueError on validation errors.
    """
    if path is not None:
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")

        if p.suffix in (".yaml", ".yml"):
            try:
                import yaml
            except ImportError:
                raise ValueError(
                    f"Cannot read '{path}': pyyaml is not installed. "
                    f"Install it with: pip install pyyaml"
                )
            with open(p) as f:
                data = yaml.safe_load(f)
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ValueError(f"{path}: expected a YAML mapping at top level")
        elif p.name == "pyproject.toml":
            with open(p, "rb") as f:
                toml_data = tomllib.load(f)
            data = toml_data.get("tool", {}).get("botaudit", {})
        else:
            # Assume YAML for any other extension
            try:
                import yaml
            except ImportError:
                raise ValueError(
                    f"Cannot read '{path}': pyyaml is not installed. "
                    f"Install it with: pip install pyyaml"
                )
            with open(p) as f:
                data = yaml.safe_load(f)
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ValueError(f"{path}: expected a YAML mapping at top level")

        return _validate(data, str(p))

    # Automatic discovery
    result = _discover(Path.cwd())
    if result is None:
        return {}
    data, source = result
    return _validate(data, source)


def load_config_for_cli(
    config_flag: str | None,
    cwd: Path | None = None,
) -> dict:
    """Load config for the CLI layer.

    *config_flag*: value of --config (None means auto-discover).
    Returns a validated config dict (possibly empty).
    Prints errors to stderr and calls sys.exit(2) on failure (FR-6.3).
    """
    if cwd is None:
        cwd = Path.cwd()

    # FR-1.6: --config none disables all loading
    if config_flag is not None and config_flag.lower() == "none":
        return {}

    try:
        if config_flag is not None:
            # FR-1.5: explicit path, skip auto-discovery
            return load_config(config_flag)
        else:
            # Auto-discover
            result = _discover(cwd)
            if result is None:
                return {}
            data, source = result
            return _validate(data, source)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"Error reading config: {exc}", file=sys.stderr)
        sys.exit(2)


def merge_config_into_args(
    args: object,
    config: dict,
    *,
    explicit_flags: set[str],
) -> None:
    """Apply config values to an argparse Namespace, respecting precedence.

    FR-3.1: CLI flags take precedence over config.
    FR-3.3: For weights, CLI --weight overrides individual categories.
    FR-3.5: Boolean defaults from argparse don't override config true values.

    *explicit_flags*: set of flag names the user actually passed on the CLI.
    """
    # Simple scalar keys: config key → argparse dest
    _KEY_MAP: dict[str, str] = {
        "format": "output_format",
        "timeout": "timeout",
        "fail_under": "fail_under",
        "quiet": "quiet",
        "no_recommendations": "no_recommendations",
        "skip_llm_discovery": "skip_llm_discovery",
        "weight_profile": "weight_profile",
        "page_type": "page_type",
        "no_page_type": "no_page_type",
    }

    for config_key, arg_dest in _KEY_MAP.items():
        if config_key not in config:
            continue
        # FR-3.1/FR-3.5: only apply config value if the CLI flag was not explicitly set
        if arg_dest in explicit_flags:
            continue
        setattr(args, arg_dest, config[config_key])

    # FR-3.3: weights are additive — config provides base, CLI overrides individual keys
    if "weights" in config and "weight_overrides" not in explicit_flags:
        # No CLI --weight flags: use config weights as override strings
        config_overrides = _parse_weights(config["weights"])
        if args.weight_overrides is None:
            args.weight_overrides = config_overrides
        # If CLI also provided some, CLI ones come last (last wins)
    elif "weights" in config and "weight_overrides" in explicit_flags:
        # CLI provided --weight flags: prepend config weights so CLI wins (last-wins)
        config_overrides = _parse_weights(config["weights"])
        cli_overrides = args.weight_overrides or []
        args.weight_overrides = config_overrides + cli_overrides
