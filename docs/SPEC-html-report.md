# BotAudit HTML Report Output Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

BotAudit currently supports three output formats: plain text (default), JSON, and CSV. These serve developer workflows well — text for quick terminal checks, JSON for programmatic consumption, and CSV for spreadsheet analysis.

However, when sharing audit results with non-technical stakeholders — clients, managers, marketing teams — these formats fall short. A self-contained HTML report provides a visual, portable, and shareable artifact that can be opened in any browser, attached to an email, or embedded in documentation without requiring any tooling.

This specification introduces `--format html` as a fourth output format. The HTML report SHALL be fully self-contained (no external dependencies) and SHALL present the same audit data as the text format in a visually structured layout.

---

## Functional Requirements

### FR-1. Format Flag

FR-1.1. The tool SHALL accept `html` as a valid value for the existing `--format` flag, in addition to `text`, `json`, and `csv`.

FR-1.2. When `--format html` is specified, the tool SHALL write a complete, self-contained HTML document to stdout.

FR-1.3. `--format html` SHALL work with single-URL, batch, and crawl modes. All existing flags (`--no-recommendations`, `--fail-under`, `--quiet`, `--timeout`, `--skip-llm-discovery`) SHALL behave unchanged.

### FR-2. Single-URL Report Content

FR-2.1. The HTML report SHALL include the following sections, in order:

| Section | Content |
|---------|---------|
| Header | Report title, audited URL (as a clickable link), overall letter grade, and overall numeric score (0–100) |
| Grade badge | A prominent visual element displaying the letter grade with color coding (see FR-3) |
| Category breakdown | One card or section per scoring category showing: category name, category score, weight, and list of findings |
| Recommendations | When `--no-recommendations` is not set, a section listing actionable recommendations grouped by category |
| Footer | Generation timestamp (UTC) and tool version |

FR-2.2. Each finding SHALL be displayed as a list item within its category section.

FR-2.3. Each recommendation SHALL display its text. If a recommendation includes a URL reference, it SHALL be rendered as a clickable link.

FR-2.4. The overall score SHALL be displayed as both a number (0–100) and a letter grade.

### FR-3. Grade Color Coding

FR-3.1. The letter grade SHALL be visually styled with a background color based on the grade tier:

| Grade | Color | Hex |
|-------|-------|-----|
| A+, A, A- | Green | `#22c55e` |
| B+, B, B- | Blue | `#3b82f6` |
| C+, C, C- | Yellow | `#eab308` |
| D+, D, D- | Orange | `#f97316` |
| F | Red | `#ef4444` |

FR-3.2. Category scores SHOULD use the same color scale applied to their individual score values.

### FR-4. Batch Mode Report

FR-4.1. In batch mode (more than one URL), the HTML report SHALL include:

| Section | Content |
|---------|---------|
| Header | Report title, total URL count, success/failure counts |
| Summary table | A table listing all URLs with their grade, score, and status — sortable by column via client-side JavaScript |
| Per-URL detail | A collapsible section for each URL containing the full single-URL report content (FR-2) |
| Footer | Generation timestamp (UTC) and tool version |

FR-4.2. Each row in the summary table SHALL link (via anchor) to the corresponding per-URL detail section.

FR-4.3. Failed URLs SHALL appear in the summary table with grade `ERR`, score `—`, and the error message.

FR-4.4. Failed URLs SHALL NOT have a detail section.

FR-4.5. Per-URL detail sections SHALL be collapsed by default. The user SHALL be able to expand them by clicking the section header or a toggle control.

FR-4.6. The summary table SHALL include an "Expand All / Collapse All" control.

### FR-5. Crawl Mode Metadata

FR-5.1. When `--crawl` was used, the HTML report header SHALL include a crawl summary showing: origin URL, number of sitemaps found, URLs discovered, URLs after filtering, and URLs after limit.

FR-5.2. Crawl metadata SHALL appear between the report header and the summary table.

### FR-6. Self-Contained Output

FR-6.1. The HTML document SHALL be fully self-contained — all CSS and JavaScript SHALL be inlined. The document SHALL NOT reference any external stylesheets, scripts, fonts, or images.

FR-6.2. The document SHALL NOT load any resources from CDNs, analytics services, or any external URL.

FR-6.3. The HTML document SHALL render correctly when opened as a local file (`file://` protocol) with no internet connection.

FR-6.4. The document SHALL use the UTF-8 character encoding and declare it in a `<meta charset="utf-8">` tag.

### FR-7. Visual Design

FR-7.1. The report SHALL use a clean, professional visual style suitable for sharing with stakeholders.

FR-7.2. The report SHALL use a light color scheme by default.

FR-7.3. The report SHOULD include a `prefers-color-scheme: dark` media query that applies a dark theme when the user's system preference is set to dark mode.

FR-7.4. The layout SHALL be responsive and SHALL render readably on viewports from 375px (mobile) to 1920px (desktop).

FR-7.5. The report SHALL use only system font stacks (`system-ui, -apple-system, sans-serif`) to avoid external font dependencies.

FR-7.6. The HTML document SHALL include a `<title>` element with the format `BotAudit Report — {url}` for single-URL mode or `BotAudit Report — Batch ({N} URLs)` for batch mode.

### FR-8. Recommendations Section

FR-8.1. When `--no-recommendations` is specified, the recommendations section SHALL be omitted entirely from the HTML output — not hidden via CSS, but absent from the DOM.

FR-8.2. When recommendations are present, they SHALL be grouped by category, matching the category order in the category breakdown.

---

## Output

### FR-9. Integration with CLI

FR-9.1. The single-URL formatter SHALL be implemented as `format_html(report: Report, *, show_recommendations: bool = True) -> str` in the `report.py` module, consistent with the existing `format_report`, `format_json`, and `format_csv` functions.

FR-9.2. The batch formatter SHALL be implemented as `format_batch_html(batch: BatchResult, *, show_recommendations: bool = True, crawl_result: CrawlResult | None = None) -> str` in the `batch.py` module, consistent with existing batch formatters.

FR-9.3. The CLI dispatch in `_run_single()` and `_run_batch()` SHALL be updated to route `--format html` to the new formatter functions.

FR-9.4. The HTML output SHALL be written to stdout via `print()`, consistent with all other format handlers. Users MAY redirect to a file with standard shell redirection (`> report.html`).

---

## Exit Codes

### FR-10. Exit Code Behavior

FR-10.1. `--format html` SHALL NOT alter exit code behavior. All exit code semantics defined in the base spec, `SPEC-batch.md`, and `SPEC-crawl.md` SHALL apply unchanged.

---

## Non-Functional Requirements

### NFR-1. Backward Compatibility

NFR-1.1. Adding `html` to the `--format` choices SHALL NOT affect the behavior of existing format values (`text`, `json`, `csv`).

NFR-1.2. No existing function signatures, module imports, or output formats SHALL change.

### NFR-2. Performance

NFR-2.1. HTML generation SHALL be performed entirely in-memory using string templating. The tool SHALL NOT write temporary files to disk.

NFR-2.2. For large batch reports (100+ URLs), the generated HTML SHOULD remain under 5 MB.

NFR-2.3. The HTML template and CSS SHALL be defined as constants or inline strings within the formatter module. The tool SHALL NOT read template files from the filesystem at runtime.

### NFR-3. HTML Quality

NFR-3.1. The generated HTML SHALL be valid HTML5.

NFR-3.2. All user-supplied content (URLs, findings text, error messages) SHALL be HTML-escaped to prevent XSS. The tool SHALL use Python's `html.escape()` or equivalent for all dynamic content inserted into the HTML.

NFR-3.3. The HTML document SHALL include appropriate semantic elements (`<header>`, `<main>`, `<section>`, `<table>`, `<details>`/`<summary>` for collapsible sections).

NFR-3.4. The document SHALL include ARIA attributes or labels where appropriate to support screen readers (e.g., `aria-label` on the grade badge, `role="table"` if using non-table markup for tabular data).

### NFR-4. Testability

NFR-4.1. The HTML formatter functions SHALL be testable by constructing `Report` and `BatchResult` objects directly, without performing HTTP requests.

NFR-4.2. Tests SHALL verify that the generated output is well-formed HTML containing expected structural elements (grade, score, categories, findings).

NFR-4.3. Tests SHALL verify that user-supplied content is properly HTML-escaped.

NFR-4.4. Tests SHALL verify that `--no-recommendations` excludes the recommendations section from the DOM entirely.

### NFR-5. Maintainability

NFR-5.1. HTML generation SHALL be implemented using Python's `html.escape()` and string formatting. The tool SHALL NOT introduce new third-party dependencies (no Jinja2, no Mako, no external template engines).

NFR-5.2. CSS SHALL be authored as a single `<style>` block within the HTML `<head>`. JavaScript (for sort/collapse behavior) SHALL be authored as a single `<script>` block before `</body>`.

NFR-5.3. The HTML template structure SHOULD be organized into helper functions (e.g., `_render_category_card()`, `_render_summary_table()`, `_render_grade_badge()`) to keep the formatter readable and each section independently maintainable.

---

## CLI Interface Summary

```
botaudit https://example.com --format html > report.html
botaudit https://example.com https://other.com --format html > batch.html
botaudit --crawl https://example.com --format html > crawl.html
botaudit --crawl https://example.com --crawl-limit 20 --format html --no-recommendations > lean.html
```

| Flag | Values | Description |
|------|--------|-------------|
| `--format` | `text`, `json`, `csv`, **`html`** | Output format (default: `text`). `html` produces a self-contained HTML document |
