# BotAudit API / Library Mode Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

BotAudit is currently a command-line tool. Every interaction flows through `cli.py` → argument parsing → pipeline → formatted stdout. This works for manual use and simple CI scripts, but breaks down for programmatic consumers:

- **CI/CD pipelines** that want to audit a URL and branch on the score without parsing text output.
- **Web services** that wrap BotAudit behind an HTTP endpoint.
- **Notebooks and scripts** where a data scientist wants to collect audit results across hundreds of pages into a DataFrame.
- **Custom tooling** that embeds BotAudit into a larger SEO or accessibility workflow.

These consumers need a stable, documented Python API — not shell-outs and JSON parsing.

This specification defines the public surface exposed by `from botaudit import ...`. It re-exports existing internal types and functions under a stable contract, adds a convenience `audit()` function, and establishes versioning and deprecation rules. No new analysis, grading, or recommendation logic is introduced — this is a packaging and contract specification that builds on the existing pipeline defined in `SPEC.md`, `SPEC-batch.md`, `SPEC-custom-weights.md`, `SPEC-page-type-heuristics.md`, and `SPEC-recommendations.md`.

---

## Functional Requirements

### FR-1. Convenience Entry Point

FR-1.1. The package SHALL expose a top-level function `audit()` with the following signature:

```python
def audit(
    url: str,
    *,
    timeout: float = 10.0,
    skip_llm_discovery: bool = False,
    no_recommendations: bool = False,
    weights: dict[str, float] | None = None,
    page_type_mode: str = "auto",
) -> Report
```

FR-1.2. `audit()` SHALL execute the full single-URL pipeline (fetch → analyze → grade → optional LLM discovery → optional page-type detection → optional recommendations), identical to the pipeline defined in `SPEC.md` §1–§7 and orchestrated by `batch.audit_one()`.

FR-1.3. On success, `audit()` SHALL return a `Report` object. On fetch failure, `audit()` SHALL raise `FetchError`. This differs from `batch.audit_one()`, which returns a `URLError` union — the library entry point uses exceptions for error signaling, which is more natural for Python callers.

FR-1.4. `audit()` SHALL be importable as:

```python
from botaudit import audit
```

FR-1.5. `audit()` SHALL NOT write to stdout or stderr. All progress messages, warnings, and errors SHALL be communicated via return values or exceptions.

FR-1.6. `audit()` SHALL NOT call `sys.exit()` under any circumstances.

### FR-2. Batch Entry Point

FR-2.1. The package SHALL expose a top-level function `audit_batch()` with the following signature:

```python
def audit_batch(
    urls: list[str],
    *,
    timeout: float = 10.0,
    skip_llm_discovery: bool = False,
    no_recommendations: bool = False,
    weights: dict[str, float] | None = None,
    page_type_mode: str = "auto",
) -> BatchResult
```

FR-2.2. `audit_batch()` SHALL process all URLs sequentially and return a `BatchResult`, identical to the behavior defined in `SPEC-batch.md` FR-4 and FR-5. Per-URL errors SHALL be captured as `URLError` entries in the result, not raised.

FR-2.3. `audit_batch()` SHALL NOT print progress messages. Callers who need progress reporting MAY iterate over URLs themselves and call `audit()` individually.

FR-2.4. `audit_batch()` SHALL NOT call `sys.exit()`. If the URL list is empty, it SHALL raise `ValueError`.

FR-2.5. `audit_batch()` SHALL be importable as:

```python
from botaudit import audit_batch
```

### FR-3. Public `__init__.py` Exports

FR-3.1. The `botaudit` package `__init__.py` SHALL export the following names, constituting the complete public API:

#### Functions

| Name | Source Module | Description |
|------|--------------|-------------|
| `audit` | `botaudit.api` | Single-URL audit (FR-1) |
| `audit_batch` | `botaudit.api` | Multi-URL audit (FR-2) |
| `resolve_weights` | `botaudit.models` | Resolve weights from profile/overrides (`SPEC-custom-weights.md` FR-3) |

#### Data Classes

| Name | Source Module | Description |
|------|--------------|-------------|
| `Report` | `botaudit.models` | Complete audit report for a URL |
| `CategoryResult` | `botaudit.models` | Score, findings, and recommendations for one category |
| `Recommendation` | `botaudit.models` | A single actionable recommendation |
| `BatchResult` | `botaudit.batch` | Aggregate result for a batch run |
| `URLSuccess` | `botaudit.batch` | Successful per-URL result wrapper |
| `URLError` | `botaudit.batch` | Failed per-URL result wrapper |
| `PageTypeResult` | `botaudit.page_type` | Page-type detection result |
| `PageTypeSignal` | `botaudit.page_type` | A signal contributing to page-type detection |

#### Enums & Types

| Name | Source Module | Description |
|------|--------------|-------------|
| `Severity` | `botaudit.models` | Recommendation severity (HIGH, MEDIUM, LOW) |

#### Exceptions

| Name | Source Module | Description |
|------|--------------|-------------|
| `FetchError` | `botaudit.fetcher` | Raised when HTTP fetch fails |

#### Constants

| Name | Source Module | Description |
|------|--------------|-------------|
| `CATEGORY_WEIGHTS` | `botaudit.models` | Default category weight dict |
| `WEIGHT_PROFILES` | `botaudit.models` | Built-in named weight profiles |
| `__version__` | `botaudit` | Package version string (FR-5) |

FR-3.2. `__init__.py` SHALL define `__all__` listing exactly the names in FR-3.1. Names not in `__all__` are internal and not part of the public API.

FR-3.3. All exports SHALL be re-imports from their source modules. `__init__.py` SHALL NOT define new classes, functions, or logic beyond the `audit()` and `audit_batch()` wrappers (which SHALL live in a new `api.py` module).

### FR-4. API Module

FR-4.1. The `audit()` and `audit_batch()` functions SHALL be implemented in a new module `botaudit/api.py`.

FR-4.2. `api.py` SHALL import from existing internal modules (`batch`, `fetcher`, `models`) and compose them. It SHALL NOT duplicate any pipeline logic.

FR-4.3. `api.py` SHALL NOT import `cli.py` or `argparse`. The API layer is independent of the CLI.

### FR-5. Package Version

FR-5.1. The package SHALL expose a `__version__` string in `__init__.py`, importable as:

```python
from botaudit import __version__
```

FR-5.2. The version string SHALL follow [Semantic Versioning 2.0.0](https://semver.org/). The initial version SHOULD be `"0.1.0"`, reflecting pre-1.0 status.

FR-5.3. The version SHALL also be accessible programmatically via `botaudit.__version__` after `import botaudit`.

### FR-6. Result Serialization Helpers

FR-6.1. The `Report` class SHALL expose a `to_dict()` method that returns a JSON-serializable `dict` with the same structure as the single-URL JSON output defined in `SPEC.md` §5.4.

FR-6.2. `to_dict()` SHALL include `page_type` when present on the report (per `SPEC-page-type-heuristics.md` FR-7.3) and omit it when `None`.

FR-6.3. `to_dict()` SHALL include `recommendations` for each category when recommendations are present. The `severity` field SHALL use the string value (e.g., `"high"`), not the enum member.

FR-6.4. The `BatchResult` class SHALL expose a `to_dict()` method that returns a JSON-serializable `dict` with the same structure as the batch JSON output defined in `SPEC-batch.md` FR-7.1.

FR-6.5. Both `to_dict()` methods SHALL accept an optional `weights` keyword argument to include weight values in category output. When `None`, the default `CATEGORY_WEIGHTS` SHALL be used.

FR-6.6. Callers MAY convert the dict to JSON via `json.dumps(report.to_dict())`. The tool SHALL NOT provide a separate `to_json()` string method — `to_dict()` is sufficient and more composable.

---

## Output Formatting

### FR-7. Format Functions

FR-7.1. The following format functions from `botaudit.report` SHALL be considered part of the public API and importable directly:

```python
from botaudit.report import format_report, format_json, format_csv, format_html
```

FR-7.2. These functions SHALL remain in `botaudit.report` — they are NOT re-exported from `__init__.py` to keep the top-level namespace focused. Callers who need formatted output import from the submodule.

FR-7.3. The batch format functions from `botaudit.batch` (`format_batch_text`, `format_batch_json`, `format_batch_csv`, `format_batch_html`) SHALL also be considered public API, importable from their module.

---

## Error Handling

### FR-8. Exception Contract

FR-8.1. `audit()` SHALL raise `FetchError` (from `botaudit.fetcher`) for all network and HTTP errors, consistent with the fetcher contract defined in `SPEC.md` §2.

FR-8.2. `audit()` SHALL NOT raise for analysis, grading, or recommendation failures — these are programming errors (bugs) and SHOULD propagate as unhandled exceptions.

FR-8.3. `audit_batch()` SHALL NOT raise for per-URL fetch failures. These SHALL be captured as `URLError` entries in the `BatchResult`, consistent with `SPEC-batch.md` FR-5.1.

FR-8.4. `audit_batch()` SHALL raise `ValueError` when called with an empty URL list.

FR-8.5. Both `audit()` and `audit_batch()` SHALL raise `ValueError` when `weights` contains invalid values (unrecognized categories, negative values, all zeros), delegating validation to `resolve_weights()` from `SPEC-custom-weights.md`.

---

## Non-Functional Requirements

### NFR-1. Backward Compatibility

NFR-1.1. The CLI SHALL continue to work identically. `cli.py` SHALL NOT be modified to import from `api.py` — the CLI and library entry points are independent consumers of the same internal modules.

NFR-1.2. Existing internal module APIs (`batch.audit_one`, `batch.run_batch`, etc.) SHALL NOT change. The public API wraps them; it does not replace them.

NFR-1.3. Adding exports to `__init__.py` SHALL NOT break existing code that imports from submodules (e.g., `from botaudit.models import Report`).

### NFR-2. Stability Contract

NFR-2.1. All names listed in `__all__` (FR-3.2) SHALL be considered stable public API. Removing or changing the signature of a public name SHALL require a major version bump.

NFR-2.2. Names NOT in `__all__` — including submodule internals, private functions (prefixed with `_`), and helper modules — are NOT part of the public API and MAY change without notice.

NFR-2.3. Adding new names to `__all__` SHALL require at minimum a minor version bump.

NFR-2.4. The `to_dict()` output structure SHALL be considered part of the public API. Changes to dict keys or value types SHALL require a major version bump.

### NFR-3. No Side Effects on Import

NFR-3.1. `import botaudit` SHALL NOT perform any I/O, network requests, or filesystem access. All imports SHALL be lazy or limited to module-level constants and class definitions.

NFR-3.2. `import botaudit` SHALL NOT print to stdout or stderr.

NFR-3.3. `import botaudit` SHALL NOT modify global state (logging configuration, signal handlers, environment variables).

### NFR-4. Performance

NFR-4.1. `audit()` SHALL have no measurable overhead beyond the underlying pipeline. The wrapper SHALL perform no additional computation beyond argument forwarding and result unwrapping.

NFR-4.2. `to_dict()` SHALL be O(n) in the number of categories and recommendations. It SHALL NOT perform deep copies or redundant serialization.

### NFR-5. Testability

NFR-5.1. `audit()` and `audit_batch()` SHALL be testable by mocking `botaudit.fetcher.fetch` to return canned HTML, avoiding real HTTP requests.

NFR-5.2. Tests SHALL verify:

**`audit()` function:**
- Returns a `Report` with correct `url`, `overall_score`, `grade`, and `categories` for a known HTML input.
- Raises `FetchError` when the fetch fails.
- Does not write to stdout or stderr.
- Does not call `sys.exit()`.
- Passes `timeout`, `skip_llm_discovery`, `no_recommendations`, `weights`, and `page_type_mode` through to the pipeline.
- Returns `page_type` on the report when `page_type_mode` is `"auto"` or an explicit type.
- Returns `page_type` as `None` when `page_type_mode` is `"disabled"`.
- Raises `ValueError` for invalid weight values.

**`audit_batch()` function:**
- Returns a `BatchResult` with correct `total`, `succeeded`, `failed` counts.
- Captures per-URL errors as `URLError` without raising.
- Raises `ValueError` for an empty URL list.
- Does not print progress messages.
- Does not call `sys.exit()`.

**`Report.to_dict()`:**
- Returns a dict matching the single-URL JSON output structure.
- Includes `page_type` when present, omits when `None`.
- Includes `recommendations` with string severity values.
- Accepts `weights` parameter for category weight output.
- Output is JSON-serializable via `json.dumps()`.

**`BatchResult.to_dict()`:**
- Returns a dict matching the batch JSON output structure.
- Includes `batch: True`, `total`, `succeeded`, `failed`, `results`.
- Error entries have `error: True` and `message`.

**Imports:**
- `from botaudit import audit` succeeds.
- `from botaudit import __version__` returns a string.
- All names in `__all__` are importable.
- `import botaudit` produces no stdout/stderr output.

### NFR-6. Maintainability

NFR-6.1. `api.py` SHALL be a thin wrapper — under 100 lines. It SHALL contain no business logic, only composition and error translation.

NFR-6.2. `__init__.py` SHALL contain only imports, `__version__`, and `__all__`. No logic, no conditionals.

NFR-6.3. When new features add public types or functions (e.g., a future config-file feature), they SHALL be added to `__all__` and documented in this specification.

---

## Data Model

### FR-9. `Report.to_dict()`

FR-9.1. The `to_dict()` method SHALL be added to the `Report` dataclass in `models.py`:

```python
@dataclass
class Report:
    url: str
    categories: list[CategoryResult]
    overall_score: float = 0.0
    grade: str = ""
    page_type: object | None = None

    def to_dict(self, *, weights: dict[str, float] | None = None) -> dict:
        """Return a JSON-serializable dict of this report."""
        ...
```

FR-9.2. The returned dict SHALL have the following structure:

```json
{
  "url": "https://example.com",
  "overall_score": 82.3,
  "grade": "B",
  "page_type": {
    "type": "article",
    "confidence": "high",
    "signals": [...]
  },
  "categories": [
    {
      "name": "Content Availability",
      "score": 90.0,
      "weight": 0.27,
      "findings": ["..."],
      "recommendations": [
        {"message": "...", "severity": "high"}
      ]
    }
  ]
}
```

FR-9.3. When `page_type` is `None`, the `page_type` key SHALL be omitted from the dict.

FR-9.4. When a category has no recommendations, the `recommendations` key SHALL be omitted from that category's dict.

### FR-10. `BatchResult.to_dict()`

FR-10.1. The `to_dict()` method SHALL be added to the `BatchResult` dataclass in `batch.py`:

```python
@dataclass
class BatchResult:
    results: list[URLResult] = field(default_factory=list)

    def to_dict(self, *, weights: dict[str, float] | None = None) -> dict:
        """Return a JSON-serializable dict of this batch result."""
        ...
```

FR-10.2. The returned dict SHALL have the same structure as `SPEC-batch.md` FR-7.1:

```json
{
  "batch": true,
  "total": 3,
  "succeeded": 2,
  "failed": 1,
  "results": [...]
}
```

FR-10.3. Success entries SHALL use `Report.to_dict()`. Error entries SHALL use the structure defined in `SPEC-batch.md` FR-7.4: `{"url": "...", "error": true, "message": "..."}`.

---

## Usage Examples

These examples are informative, not normative.

### Single URL

```python
from botaudit import audit, FetchError

try:
    report = audit("https://example.com")
except FetchError as e:
    print(f"Could not fetch: {e}")
    raise SystemExit(1)

print(f"Grade: {report.grade} ({report.overall_score}/100)")

for cat in report.categories:
    print(f"  {cat.name}: {cat.score}")

if report.page_type:
    print(f"Page type: {report.page_type.page_type}")
```

### Batch

```python
from botaudit import audit_batch, URLSuccess, URLError

result = audit_batch([
    "https://example.com",
    "https://example.com/blog/post-1",
    "https://example.com/products/widget",
])

for r in result.results:
    if isinstance(r, URLSuccess):
        print(f"{r.url}: {r.report.grade}")
    elif isinstance(r, URLError):
        print(f"{r.url}: ERROR - {r.message}")
```

### Custom Weights

```python
from botaudit import audit, resolve_weights

weights = resolve_weights(profile="ecommerce")
report = audit("https://shop.example.com/product/123", weights=weights)
```

### JSON Serialization

```python
import json
from botaudit import audit

report = audit("https://example.com")
data = report.to_dict()
print(json.dumps(data, indent=2))
```
