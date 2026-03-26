# BotAudit Batch URL Scanning Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

BotAudit currently accepts a single URL per invocation (§1.3). This is sufficient for ad-hoc checks but inadequate for real-world workflows — teams maintain dozens or hundreds of pages that need periodic auditing, CI pipelines run against staging environments with multiple entry points, and consultants audit entire sites for clients.

Batch URL scanning allows users to audit multiple URLs in one invocation, either by passing them directly on the command line or by reading them from a file. Each URL receives a full, independent audit. Results are reported individually and summarized collectively.

This specification extends the input model defined in §1 and the output model defined in §5 while preserving full backward compatibility with single-URL invocations.

---

## Functional Requirements

### FR-1. Input Sources

FR-1.1. The tool SHALL accept one or more URLs as positional command-line arguments.

FR-1.2. The tool SHALL accept a `--file` (`-f`) option whose value is a path to a text file containing URLs to audit.

FR-1.3. When `--file -` is specified, the tool SHALL read URLs from standard input.

FR-1.4. The tool SHALL accept both positional URLs and `--file` in the same invocation. All URLs from both sources SHALL be combined into a single batch.

FR-1.5. When no positional URLs are provided and `--file` is not specified, the tool SHALL print a usage error and exit with code 2, consistent with current behavior.

FR-1.6. A single positional URL with no `--file` option SHALL behave identically to the current single-URL mode — no summary table, no progress output, no change to existing output format.

### FR-2. URL File Format

FR-2.1. The URL file SHALL contain one URL per line.

FR-2.2. Lines that are empty or contain only whitespace SHALL be ignored.

FR-2.3. Lines whose first non-whitespace character is `#` SHALL be treated as comments and ignored.

FR-2.4. Leading and trailing whitespace on each line SHALL be stripped before validation.

FR-2.5. Each non-comment, non-empty line SHALL be validated using the same rules as positional URL arguments (scheme MUST be `http` or `https`, netloc MUST be present).

FR-2.6. If a line fails URL validation, the tool SHALL print a warning to stderr identifying the line number and invalid value, skip that line, and continue processing the remaining lines.

FR-2.7. The tool SHALL reject a file that produces zero valid URLs after parsing and SHALL exit with code 2.

FR-2.8. The file SHALL be read with UTF-8 encoding. The tool SHOULD handle a UTF-8 BOM if present.

### FR-3. Deduplication

FR-3.1. When the combined URL list (positional + file) contains duplicate URLs, the tool SHALL deduplicate them, auditing each unique URL exactly once.

FR-3.2. Deduplication SHALL be case-sensitive and SHALL compare URLs as-is after whitespace stripping. The tool SHALL NOT normalize URLs (e.g., removing trailing slashes or default ports).

FR-3.3. When duplicates are removed, the tool SHOULD print a message to stderr indicating how many duplicates were skipped.

### FR-4. Execution

FR-4.1. Each URL in the batch SHALL receive a full, independent audit — the same fetch, analysis, grading, and recommendation pipeline as a single-URL invocation.

FR-4.2. The tool SHALL process URLs sequentially in the order they appear (positional arguments first, then file entries, after deduplication).

FR-4.3. The tool MAY support concurrent auditing of multiple URLs in a future version via an optional `--concurrency` flag. This specification does not define concurrency behavior.

FR-4.4. All existing flags (`--timeout`, `--format`, `--no-recommendations`, `--skip-llm-discovery`, `--fail-under`) SHALL apply uniformly to every URL in the batch.

### FR-5. Per-URL Error Handling

FR-5.1. If a URL fails during fetching (network error, HTTP error, timeout), the tool SHALL log the error to stderr, record the URL as failed, and continue processing the remaining URLs.

FR-5.2. A failed URL SHALL NOT cause the tool to exit early or abort the batch.

FR-5.3. A failed URL SHALL appear in the output and summary with an error indicator rather than a grade.

FR-5.4. If ALL URLs in the batch fail, the tool SHALL exit with code 1.

FR-5.5. If at least one URL succeeds, the tool SHALL NOT exit with code 1 solely because other URLs failed (but see FR-7 for `--fail-under` interaction).

---

## Output

### FR-6. Text Format

FR-6.1. In batch mode (more than one URL), the text formatter SHALL produce one complete report per URL, using the same format defined in §5.

FR-6.2. Individual reports SHALL be separated by a blank line and a full-width separator.

FR-6.3. After all individual reports, the tool SHALL print a summary table containing the following columns:

| Column | Description |
|--------|-------------|
| URL | The audited URL |
| Grade | The letter grade, or `ERR` if the URL failed |
| Score | The overall score (0–100), or `—` if the URL failed |

FR-6.4. The summary table SHALL be preceded by a header line: `Batch Summary (N URLs)` where N is the total count of unique URLs attempted.

FR-6.5. The summary table SHALL include a row for each URL in processing order.

FR-6.6. Failed URLs SHALL appear in the summary table with grade `ERR` and score `—`, followed by a brief error reason.

### FR-7. JSON Format

FR-7.1. In batch mode, the JSON output SHALL be a single object with the following top-level keys:

| Key | Type | Description |
|-----|------|-------------|
| `batch` | `boolean` | Always `true` in batch mode |
| `total` | `integer` | Total number of unique URLs attempted |
| `succeeded` | `integer` | Number of URLs that completed successfully |
| `failed` | `integer` | Number of URLs that failed |
| `results` | `array` | Array of per-URL result objects |

FR-7.2. Each element in `results` SHALL be either a success object or an error object.

FR-7.3. A success object SHALL have the same structure as the current single-URL JSON output (fields: `url`, `overall_score`, `grade`, `categories`).

FR-7.4. An error object SHALL have the following structure:

```json
{
  "url": "https://example.com",
  "error": true,
  "message": "Connection timed out"
}
```

FR-7.5. When a single URL is audited (non-batch mode), the JSON output SHALL remain unchanged from the current format — no `batch` wrapper.

### FR-8. CSV Format

FR-8.1. In batch mode, the CSV output SHALL contain one header row followed by data rows for all URLs, consistent with the current per-category row structure.

FR-8.2. Successful URLs SHALL produce category rows identical to the current single-URL CSV output.

FR-8.3. Failed URLs SHALL produce a single row with the URL, `ERR` as the grade, `0` as the overall score, `error` as the category, and the error message in the findings column.

FR-8.4. The CSV header row SHALL appear exactly once, regardless of the number of URLs.

---

## Exit Codes

### FR-9. Exit Code Behavior

FR-9.1. In batch mode, the tool SHALL exit with code 0 if at least one URL succeeds and no `--fail-under` violation occurs.

FR-9.2. The tool SHALL exit with code 1 if ALL URLs in the batch fail.

FR-9.3. When `--fail-under` is specified, the tool SHALL exit with code 1 if ANY successfully audited URL's grade falls below the threshold.

FR-9.4. Failed URLs SHALL NOT be evaluated against `--fail-under`. Only successfully audited URLs are compared.

FR-9.5. When `--fail-under` is specified and ALL URLs fail (none can be graded), the tool SHALL exit with code 1.

FR-9.6. The tool SHALL exit with code 2 for input errors (no URLs provided, invalid flags, unreadable file).

---

## Progress Reporting

### FR-10. Progress Output

FR-10.1. In batch mode with text output, the tool SHOULD print progress messages to stderr as each URL begins processing, in the format: `[N/T] Auditing URL...` where N is the current index and T is the total count.

FR-10.2. Progress messages SHALL be written to stderr, not stdout, to preserve clean output for piping and redirection.

FR-10.3. The tool MAY accept a `--quiet` (`-q`) flag to suppress progress messages.

FR-10.4. In single-URL mode, the tool SHALL NOT print progress messages, preserving current behavior.

---

## Non-Functional Requirements

### NFR-1. Backward Compatibility

NFR-1.1. A single positional URL with no `--file` flag SHALL produce output byte-for-byte identical to the current tool output. Batch mode is activated only when more than one URL is present.

NFR-1.2. The positional `url` argument SHALL change from required-single to accepting one or more values. The tool SHALL NOT break existing shell scripts or CI configurations that pass a single URL.

NFR-1.3. Existing flags SHALL NOT change their syntax, defaults, or behavior when used with a single URL.

### NFR-2. Performance

NFR-2.1. Sequential batch processing SHALL NOT introduce per-URL overhead beyond what a single invocation requires. There SHALL be no artificial delays between URLs.

NFR-2.2. The tool SHOULD reuse HTTP client resources (connection pools, client instances) across URLs in the batch where the underlying HTTP library supports it.

NFR-2.3. For large batches, memory usage SHOULD scale linearly with the number of URLs. The tool SHOULD NOT hold all fetched HTML in memory simultaneously — each URL's resources SHOULD be released after its audit completes.

### NFR-3. Limits

NFR-3.1. The tool SHALL NOT impose a hard maximum on batch size.

NFR-3.2. The tool SHOULD print a warning to stderr when the batch exceeds 100 URLs, informing the user that the run may take a while.

### NFR-4. Robustness

NFR-4.1. The tool SHALL NOT crash or produce a stack trace if the URL file does not exist, is not readable, or is a directory. These conditions SHALL produce a clear error message and exit with code 2.

NFR-4.2. The tool SHALL handle URL files up to at least 10,000 lines without failure.

NFR-4.3. The tool SHALL NOT crash if the URL file contains binary content. Non-UTF-8 files SHALL produce a clear error message and exit with code 2.

### NFR-5. Testability

NFR-5.1. The batch input parsing logic (file reading, validation, deduplication) SHALL be implemented as pure functions that accept input and return a list of URLs, testable without performing any HTTP requests.

NFR-5.2. The batch orchestration logic SHALL be testable by injecting a mock audit function, verifying that each URL is processed and errors are handled correctly.

NFR-5.3. The summary formatting logic SHALL be testable independently by constructing result objects directly.

### NFR-6. Maintainability

NFR-6.1. Batch orchestration SHALL be implemented in a dedicated module (`batch.py` or equivalent), separate from the existing `cli.py` entry point. The CLI module SHALL delegate to the batch module when multiple URLs are detected.

NFR-6.2. The single-URL code path SHALL NOT be modified to accommodate batch logic. Batch mode SHALL wrap the existing single-URL pipeline rather than replacing it.

NFR-6.3. The batch module SHALL NOT import or depend on modules beyond what `cli.py` already uses, plus Python standard library modules (`pathlib`, `typing`).
