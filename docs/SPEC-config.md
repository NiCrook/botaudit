# BotAudit Configuration File Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

Every configurable behavior in BotAudit — output format, weight profiles, page-type mode, timeout, fail-under — is currently set via CLI flags. This works for one-off invocations, but creates friction in two common scenarios:

- **Project-level defaults.** A team that always uses `--weight-profile ecommerce --format json --fail-under B` must pass those flags in every CI step, script, and developer alias. Forgetting one flag produces inconsistent results.
- **Shareable configuration.** A project's audit policy (weights, thresholds, skipped checks) is tribal knowledge scattered across Makefiles and CI YAML. There is no single source of truth that lives in the repository.

A configuration file solves both problems: a checked-in `.botaudit.yaml` or `[tool.botaudit]` table in `pyproject.toml` declares the project's audit policy once, and every invocation inherits it automatically.

This specification defines how BotAudit discovers, parses, validates, and merges configuration from files. It does not introduce new audit behavior — every key maps to an existing CLI flag defined in `SPEC.md`, `SPEC-batch.md`, `SPEC-custom-weights.md`, `SPEC-crawl.md`, `SPEC-page-type-heuristics.md`, and `SPEC-ai-metadata.md`.

---

## Functional Requirements

### FR-1. Configuration Sources

FR-1.1. BotAudit SHALL support configuration from two file-based sources:

| Source | Location | Format |
|--------|----------|--------|
| `.botaudit.yaml` | Project root (working directory) | YAML |
| `pyproject.toml` | Project root (working directory), under `[tool.botaudit]` | TOML |

FR-1.2. BotAudit SHALL search for configuration files in the current working directory at invocation time. It SHALL NOT walk parent directories.

FR-1.3. If both `.botaudit.yaml` and a `[tool.botaudit]` table in `pyproject.toml` exist, BotAudit SHALL exit with an error and print a diagnostic message naming both files. The tool SHALL NOT attempt to merge configurations from multiple file sources.

FR-1.4. If neither file is found, BotAudit SHALL proceed with built-in defaults. The absence of a configuration file SHALL NOT produce a warning.

FR-1.5. BotAudit MAY support an explicit `--config PATH` flag to load a YAML configuration file from an arbitrary path. When `--config` is provided, automatic discovery (FR-1.2) SHALL be skipped entirely.

FR-1.6. The `--config` flag SHALL accept the special value `none` (case-insensitive) to disable all configuration file loading, including automatic discovery.

### FR-2. Configuration Keys

FR-2.1. The following keys SHALL be recognized in the configuration file. Each key corresponds to an existing CLI flag:

| Config Key | CLI Equivalent | Type | Default | Description |
|------------|---------------|------|---------|-------------|
| `format` | `--format` | string | `"text"` | Output format: `text`, `json`, `csv`, `html` |
| `timeout` | `--timeout` | float | `10.0` | HTTP request timeout in seconds |
| `fail_under` | `--fail-under` | string | — | Minimum passing grade: `A`, `B`, `C`, `D`, `F` |
| `quiet` | `--quiet` | bool | `false` | Suppress progress messages |
| `no_recommendations` | `--no-recommendations` | bool | `false` | Suppress recommendations in output |
| `skip_llm_discovery` | `--skip-llm-discovery` | bool | `false` | Skip LLM discoverability analysis |
| `weight_profile` | `--weight-profile` | string | — | Named weight profile (e.g., `ecommerce`, `docs`) |
| `weights` | `--weight` | mapping | — | Per-category weight overrides (see FR-2.3) |
| `page_type` | `--page-type` | string | `"auto"` | Force page type or `auto` |
| `no_page_type` | `--no-page-type` | bool | `false` | Disable page-type detection entirely |

FR-2.2. Unrecognized keys SHALL cause the tool to exit with an error listing each unknown key. This prevents silent misconfiguration from typos.

FR-2.3. The `weights` key SHALL be a mapping of category names (or aliases per `SPEC-custom-weights.md` FR-1.3) to numeric values. Values MAY be expressed as decimals (`0.30`) or percentages (`"30%"`). Example:

```yaml
weights:
  structured-data: 0.25
  llm: "30%"
  content: 0.20
```

FR-2.4. The `weights` key and `weight_profile` key MAY coexist. When both are present, `weight_profile` SHALL be applied first as the base, then `weights` SHALL override individual categories on top — identical to the CLI behavior of `--weight-profile` + `--weight` defined in `SPEC-custom-weights.md` FR-3.

FR-2.5. Boolean keys SHALL accept YAML boolean values (`true`/`false`). In `pyproject.toml`, they SHALL be TOML booleans. String representations (e.g., `"yes"`, `"on"`) SHALL NOT be accepted.

### FR-3. Precedence

FR-3.1. When the same setting is specified in both a configuration file and a CLI flag, the CLI flag SHALL take precedence. Configuration files provide defaults; CLI flags override them.

FR-3.2. The full precedence order, from highest to lowest priority, SHALL be:

1. CLI flags (explicit invocation)
2. Configuration file (`.botaudit.yaml` or `[tool.botaudit]`)
3. Built-in defaults

FR-3.3. For additive settings (`weights`), CLI `--weight` flags SHALL override individual categories from the config file, not replace the entire mapping. Example: if the config file sets `weights: {content: 0.30, llm: 0.20}` and the CLI passes `--weight llm=0.15`, the resolved weights SHALL be `{content: 0.30, llm: 0.15}` with all other categories at their profile or default values.

FR-3.4. For `weight_profile`, the CLI `--weight-profile` SHALL replace the config file's `weight_profile` entirely. It SHALL NOT stack profiles.

FR-3.5. Boolean flags that default to `false` (e.g., `quiet`, `no_recommendations`) SHALL be considered "set" by a CLI flag only when the flag is explicitly passed. The mere presence of a default `false` in argparse SHALL NOT override a `true` in the config file.

### FR-4. YAML Format

FR-4.1. The `.botaudit.yaml` file SHALL be a single YAML document containing a flat mapping at the top level.

FR-4.2. The file SHALL be parsed with a YAML 1.2 compatible parser. BotAudit SHOULD use `tomllib` (stdlib) for TOML and add `pyyaml` as a dependency for YAML.

FR-4.3. Example `.botaudit.yaml`:

```yaml
format: json
timeout: 15.0
fail_under: B
quiet: true
weight_profile: ecommerce
weights:
  llm: 0.20
page_type: auto
```

### FR-5. TOML Format (`pyproject.toml`)

FR-5.1. Configuration in `pyproject.toml` SHALL live under the `[tool.botaudit]` table, following the `pyproject.toml` convention for tool-specific configuration.

FR-5.2. Keys and types SHALL be identical to the YAML format (FR-2.1). The `weights` key SHALL be a TOML inline table or standard table.

FR-5.3. BotAudit SHALL parse `pyproject.toml` using `tomllib` from the Python standard library (Python 3.11+). No additional TOML dependency is required.

FR-5.4. Example `pyproject.toml`:

```toml
[tool.botaudit]
format = "json"
timeout = 15.0
fail_under = "B"
quiet = true
weight_profile = "ecommerce"

[tool.botaudit.weights]
llm = 0.20
```

### FR-6. Validation

FR-6.1. Configuration files SHALL be validated after parsing and before merging with CLI flags.

FR-6.2. The following conditions SHALL cause an error with a descriptive message:

- Unrecognized key (FR-2.2)
- `format` value not in `{text, json, csv, html}`
- `fail_under` value not in `{A, B, C, D, F}`
- `timeout` is not a positive number
- `weight_profile` names an unknown profile
- `weights` contains an unrecognized category name or alias
- `weights` contains a negative value or non-numeric value
- `page_type` names an unknown type
- `no_page_type` and `page_type` are both set (mutual exclusion, per `SPEC-page-type-heuristics.md` FR-6)
- YAML or TOML syntax error

FR-6.3. Validation errors SHALL print to stderr and exit with code 2, consistent with argparse validation behavior.

FR-6.4. The error message SHALL include the file path and the specific key that failed validation.

### FR-7. Library API Integration

FR-7.1. The `audit()` and `audit_batch()` functions (defined in `SPEC-library-mode.md`) SHALL NOT read configuration files. The library API is explicit — all options are passed as function arguments. Configuration files are a CLI-only concern.

FR-7.2. The library API MAY expose a `load_config()` function for callers who want to read and apply a config file programmatically:

```python
def load_config(
    path: str | None = None,
) -> dict[str, object]:
    """Load and validate a botaudit configuration file.

    When *path* is None, uses automatic discovery (FR-1.2).
    Returns a dict of validated configuration values.
    Raises FileNotFoundError when *path* is given but does not exist.
    Raises ValueError on validation errors.
    """
    ...
```

FR-7.3. `load_config()` SHALL be importable as:

```python
from botaudit import load_config
```

FR-7.4. `load_config()` SHALL return a dict with only recognized keys (FR-2.1) and validated values. The dict MAY be unpacked into `audit()` or `audit_batch()` keyword arguments where keys overlap.

---

## Exit Codes

| Code | Condition |
|------|-----------|
| 0 | Normal execution |
| 1 | Grade below `fail_under` threshold |
| 2 | Configuration file error (syntax, validation, conflicting sources) |

---

## Non-Functional Requirements

### NFR-1. Backward Compatibility

NFR-1.1. All existing CLI invocations without a configuration file SHALL produce identical results. The feature is purely additive.

NFR-1.2. When no configuration file is found, the tool SHALL behave exactly as it does today — no warnings, no changed defaults, no performance impact.

NFR-1.3. The `--config none` escape hatch (FR-1.6) ensures users can always disable config file loading in environments where an unwanted config file may be present.

### NFR-2. Dependencies

NFR-2.1. TOML parsing SHALL use `tomllib` from the standard library (Python 3.11+). No new dependency is required for TOML support.

NFR-2.2. YAML parsing SHOULD use `pyyaml`. This adds one new dependency to `pyproject.toml`.

NFR-2.3. If `pyyaml` is not installed and the user has a `.botaudit.yaml` file, the tool SHALL exit with a clear error message suggesting `pip install pyyaml` or switching to `pyproject.toml`.

### NFR-3. Performance

NFR-3.1. Configuration file discovery and parsing SHALL add no more than 10ms to startup time for typical files (under 1KB).

NFR-3.2. Configuration SHALL be loaded once at startup and passed through the pipeline. It SHALL NOT be re-read per URL.

### NFR-4. Security

NFR-4.1. The YAML parser SHALL use safe loading (`yaml.safe_load`). Arbitrary Python object deserialization SHALL NOT be permitted.

NFR-4.2. Configuration files SHALL NOT support environment variable interpolation, shell expansion, or any form of dynamic evaluation.

### NFR-5. Testability

NFR-5.1. Configuration loading SHALL be testable independently of the CLI by calling `load_config()` with an explicit path.

NFR-5.2. Tests SHALL verify:

**Discovery:**
- `.botaudit.yaml` is found and loaded when present.
- `[tool.botaudit]` in `pyproject.toml` is found and loaded when present.
- Both present → error exit with diagnostic.
- Neither present → built-in defaults, no warning.
- `--config path/to/file.yaml` loads the specified file.
- `--config none` disables all config loading.

**Parsing:**
- All keys from FR-2.1 are accepted in both YAML and TOML formats.
- `weights` mapping is parsed correctly with decimal and percentage values.
- YAML syntax error → exit 2 with message.
- TOML syntax error → exit 2 with message.

**Validation:**
- Unrecognized key → error naming the key.
- Invalid `format` value → error.
- Invalid `fail_under` value → error.
- Negative timeout → error.
- Unknown weight profile → error.
- Unknown category in `weights` → error.
- Negative weight value → error.
- `no_page_type: true` + `page_type: article` → mutual exclusion error.

**Precedence:**
- CLI `--format json` overrides config `format: text`.
- CLI `--weight llm=0.15` overrides config `weights: {llm: 0.20}` for that category only.
- CLI `--weight-profile docs` replaces config `weight_profile: ecommerce` entirely.
- Config `quiet: true` is honored when `--quiet` is not passed on CLI.
- Config `quiet: true` is NOT overridden by argparse default `false`.

**Library API:**
- `audit()` and `audit_batch()` do not read config files.
- `load_config()` returns a valid dict for a well-formed file.
- `load_config()` raises `ValueError` for invalid content.
- `load_config(None)` uses automatic discovery.

---

## CLI Interface Summary

These examples are informative, not normative.

```
botaudit https://example.com                          # uses .botaudit.yaml or pyproject.toml if present
botaudit https://example.com --config my-config.yaml  # explicit config file
botaudit https://example.com --config none             # ignore all config files
```

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--config` | — | `PATH \| none` | — | Load config from PATH, or `none` to disable discovery |
