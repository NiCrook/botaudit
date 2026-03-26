# BotAudit Custom Weight Profiles Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

BotAudit scores pages across six categories, each assigned a fixed weight that determines its contribution to the overall score:

| Category | Default Weight |
|----------|---------------|
| Content Availability | 27% |
| Semantic HTML | 23% |
| Link Discoverability | 18% |
| Structured Data | 13% |
| LLM Discoverability | 10% |
| Metadata & Discoverability | 9% |

These defaults reflect a general-purpose view of what matters most for AI-accessible pages. However, different contexts call for different priorities. An e-commerce team may care more about structured data (product schema) than semantic HTML. A documentation site may prioritize content availability and link discoverability above all else. A team preparing for AI agent integration may want to heavily weight LLM discoverability.

This specification introduces two mechanisms for overriding default weights: a `--weight` CLI flag for ad-hoc per-category overrides, and a `--weight-profile` flag for selecting named presets. Both mechanisms feed into the existing weighted-average scoring pipeline without altering per-category scores or any other tool behavior.

---

## Functional Requirements

### FR-1. Per-Category Weight Override (`--weight`)

FR-1.1. The tool SHALL accept a `--weight` (`-w`) flag that takes a single argument in the format `CATEGORY=VALUE`, where `CATEGORY` is a category name and `VALUE` is a numeric weight.

FR-1.2. `--weight` MAY be specified multiple times to override multiple categories in a single invocation:

```
botaudit https://example.com --weight "Structured Data=0.30" --weight "Semantic HTML=0.10"
```

FR-1.3. `CATEGORY` SHALL be matched case-insensitively against the canonical category names. The tool SHALL accept the following aliases in addition to the full canonical names:

| Canonical Name | Accepted Aliases |
|---------------|-----------------|
| Content Availability | `content`, `content-availability` |
| Semantic HTML | `semantic`, `semantic-html` |
| Link Discoverability | `links`, `link-discoverability` |
| Structured Data | `structured`, `structured-data` |
| LLM Discoverability | `llm`, `llm-discoverability` |
| Metadata & Discoverability | `metadata`, `meta` |

FR-1.4. `VALUE` SHALL be a non-negative number. It MAY be expressed as a decimal proportion (e.g., `0.30`) or as a percentage with a trailing `%` sign (e.g., `30%`). Both forms SHALL be treated equivalently — `0.30` and `30%` both represent 30% weight.

FR-1.5. If a `CATEGORY` name does not match any known category or alias (after case-insensitive matching), the tool SHALL print an error to stderr listing the unrecognized name and the valid category names, then exit with code 2.

FR-1.6. If the same category is specified more than once via `--weight`, the last value SHALL win. The tool SHOULD print a warning to stderr noting the duplicate.

FR-1.7. Categories not overridden via `--weight` SHALL retain their default weights.

### FR-2. Weight Profiles (`--weight-profile`)

FR-2.1. The tool SHALL accept a `--weight-profile` (`-W`) flag that takes a single named profile as its value. A weight profile is a predefined set of category weights.

FR-2.2. The tool SHALL ship with the following built-in profiles:

| Profile Name | Description | Weights |
|-------------|-------------|---------|
| `default` | Standard weights (same as no flag) | Content Availability: 27%, Semantic HTML: 23%, Link Discoverability: 18%, Structured Data: 13%, LLM Discoverability: 10%, Metadata & Discoverability: 9% |
| `ecommerce` | Emphasizes structured data and metadata for product pages | Content Availability: 20%, Semantic HTML: 15%, Link Discoverability: 15%, Structured Data: 25%, LLM Discoverability: 10%, Metadata & Discoverability: 15% |
| `docs` | Prioritizes content and navigation for documentation sites | Content Availability: 30%, Semantic HTML: 25%, Link Discoverability: 25%, Structured Data: 5%, LLM Discoverability: 10%, Metadata & Discoverability: 5% |
| `ai-ready` | Maximizes AI/LLM accessibility signals | Content Availability: 20%, Semantic HTML: 15%, Link Discoverability: 10%, Structured Data: 20%, LLM Discoverability: 25%, Metadata & Discoverability: 10% |

FR-2.3. `--weight-profile` SHALL NOT be specified more than once. If provided multiple times, the tool SHALL print an error and exit with code 2.

FR-2.4. If the profile name does not match any built-in profile (case-insensitive), the tool SHALL print an error to stderr listing the unrecognized name and the available profile names, then exit with code 2.

FR-2.5. `--weight-profile` and `--weight` MAY be combined. When both are present, the profile SHALL be applied first, then individual `--weight` overrides SHALL be applied on top. This allows users to start from a profile and fine-tune specific categories:

```
botaudit https://example.com --weight-profile ecommerce --weight "LLM Discoverability=0.20"
```

### FR-3. Weight Validation

FR-3.1. After resolving the final weight set (defaults, profile, and/or overrides), the tool SHALL validate that all weights are non-negative. A weight of `0` is permitted and means the category is excluded from the overall score but still analyzed and reported.

FR-3.2. The tool SHALL validate that at least one category has a weight greater than zero. If all weights are zero, the tool SHALL print an error to stderr and exit with code 2.

FR-3.3. The final weights SHALL be normalized to sum to 1.0 before scoring. This normalization is already performed by the existing `compute_grade()` method (division by total weight), so no change to that method is required.

FR-3.4. A `VALUE` that is not a valid non-negative number (e.g., `abc`, `-5`, `--`) SHALL cause the tool to print an error to stderr and exit with code 2.

### FR-4. Interaction with `--skip-llm-discovery`

FR-4.1. When `--skip-llm-discovery` is active, the LLM Discoverability category is omitted entirely. Any `--weight` override for LLM Discoverability SHALL be silently ignored in this case — the weight is irrelevant since the category produces no score.

FR-4.2. When `--skip-llm-discovery` is active and a `--weight-profile` is used, the profile's LLM Discoverability weight SHALL be ignored and the remaining weights SHALL be renormalized, consistent with existing behavior.

### FR-5. Listing Available Profiles

FR-5.1. The tool SHALL accept a `--list-profiles` flag that prints all available weight profiles to stdout and exits with code 0.

FR-5.2. The output of `--list-profiles` SHALL display each profile's name, description, and weight distribution in a human-readable table format:

```
Available weight profiles:

  default       Standard weights
                  Content Availability: 27%  Semantic HTML: 23%
                  Link Discoverability: 18%  Structured Data: 13%
                  LLM Discoverability: 10%   Metadata & Discoverability: 9%

  ecommerce     Emphasizes structured data and metadata for product pages
                  Content Availability: 20%  Semantic HTML: 15%
                  Link Discoverability: 15%  Structured Data: 25%
                  LLM Discoverability: 10%   Metadata & Discoverability: 15%

  ...
```

FR-5.3. When `--list-profiles` is specified, the tool SHALL NOT require any URL arguments.

---

## Output

### FR-6. Weight Display in Reports

FR-6.1. When non-default weights are in effect, all output formats SHALL reflect the active weights — not the built-in defaults. This applies to the weight percentage shown in text output, the `weight` field in JSON output, and the weight column in CSV output.

FR-6.2. In text output, the tool SHOULD append a note after the header indicating that custom weights are active:

```
Weights: ecommerce profile
```

or, when using `--weight` overrides only:

```
Weights: custom
```

FR-6.3. In JSON output, the batch/single-URL wrapper object SHALL include a `weights` key when non-default weights are active:

```json
{
  "weights": {
    "profile": "ecommerce",
    "overrides": {
      "LLM Discoverability": 0.20
    },
    "resolved": {
      "Content Availability": 0.20,
      "Semantic HTML": 0.15,
      "Link Discoverability": 0.15,
      "Structured Data": 0.25,
      "LLM Discoverability": 0.20,
      "Metadata & Discoverability": 0.15
    }
  }
}
```

FR-6.4. The `weights.profile` key SHALL be present only when `--weight-profile` was used. The `weights.overrides` key SHALL be present only when `--weight` was used. The `weights.resolved` key SHALL always be present in the `weights` object, showing the final normalized weights applied.

FR-6.5. In CSV output, the `weight` column SHALL reflect the active weights. No additional weight metadata columns are required.

FR-6.6. In HTML output, the category cards SHALL display the active weights. When non-default weights are in effect, the report header SHOULD include a note indicating the profile and/or custom weights in use.

---

## Exit Codes

### FR-7. Exit Code Behavior

FR-7.1. Custom weights SHALL NOT alter exit code behavior. All exit code semantics defined in the base spec, `SPEC-batch.md`, and `SPEC-crawl.md` SHALL apply unchanged.

FR-7.2. Invalid weight arguments (unrecognized category, non-numeric value, unrecognized profile) SHALL exit with code 2 (argument error), consistent with other argument validation failures.

---

## Non-Functional Requirements

### NFR-1. Backward Compatibility

NFR-1.1. When neither `--weight` nor `--weight-profile` is specified, the tool SHALL behave identically to its current behavior. Default weights, scoring, and output SHALL be unchanged.

NFR-1.2. The existing `CATEGORY_WEIGHTS` constant in `models.py` SHALL remain as the single source of truth for default weights. The custom weights mechanism SHALL layer on top of these defaults without modifying the constant.

NFR-1.3. No existing function signatures in the public API SHALL change. New parameters SHALL use keyword arguments with defaults that preserve current behavior.

### NFR-2. Performance

NFR-2.1. Weight resolution (profile lookup, override application, normalization) SHALL be performed once at startup before any HTTP requests. It SHALL NOT be repeated per-URL in batch mode.

NFR-2.2. Weight profiles SHALL be defined as in-memory constants. The tool SHALL NOT read profile definitions from the filesystem at runtime.

### NFR-3. Maintainability

NFR-3.1. Weight profiles and resolution logic SHALL be implemented in the existing `models.py` module alongside `CATEGORY_WEIGHTS`, keeping all weight-related definitions co-located.

NFR-3.2. Each built-in profile SHALL be defined as a dictionary constant with the same shape as `CATEGORY_WEIGHTS`. A registry mapping profile names to their weight dictionaries SHALL provide the lookup mechanism.

NFR-3.3. The weight resolution function SHALL have the signature:

```python
def resolve_weights(
    *,
    profile: str | None = None,
    overrides: list[str] | None = None,
) -> dict[str, float]:
```

It SHALL return a dictionary with the same keys as `CATEGORY_WEIGHTS`, representing the final resolved (but not yet normalized) weights. Normalization occurs at scoring time via the existing `compute_grade()` division.

NFR-3.4. Adding a new built-in profile SHALL require only adding a new constant dictionary and a single entry in the profile registry. No other code changes SHALL be necessary.

### NFR-4. Testability

NFR-4.1. The `resolve_weights()` function SHALL be testable as a pure function — given a profile name and/or override strings, it returns a weight dictionary. No HTTP requests, no side effects.

NFR-4.2. Tests SHALL verify that:
- Default weights are returned when no profile or overrides are specified.
- Each built-in profile returns its documented weights.
- `--weight` overrides replace individual category weights.
- Profile + override combination applies overrides on top of the profile.
- Case-insensitive matching works for category names and aliases.
- Percentage syntax (`30%`) and decimal syntax (`0.30`) produce equivalent results.
- Unrecognized category names raise an appropriate error.
- Unrecognized profile names raise an appropriate error.
- Duplicate `--weight` entries for the same category use the last value.
- All-zero weights raise an appropriate error.
- A weight of zero for a single category is accepted and excludes that category from the overall score.

NFR-4.3. Integration tests SHALL verify that custom weights propagate through the full pipeline — from CLI argument parsing through scoring to output display — and that the overall score changes appropriately when weights are altered.

---

## CLI Interface Summary

```
botaudit https://example.com --weight "Structured Data=0.30"
botaudit https://example.com -w "content=0.40" -w "semantic=0.10"
botaudit https://example.com --weight "llm=25%"
botaudit https://example.com --weight-profile ecommerce
botaudit https://example.com -W ai-ready --format json
botaudit https://example.com --weight-profile docs --weight "llm=0.20"
botaudit --list-profiles
```

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--weight` | `-w` | `CATEGORY=VALUE` (repeatable) | — | Override the weight for a specific category. Value is a decimal (0.30) or percentage (30%) |
| `--weight-profile` | `-W` | string | — | Use a named weight profile as the base weights |
| `--list-profiles` | | flag | — | List available weight profiles and exit |
