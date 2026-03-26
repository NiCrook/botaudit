"""Batch URL scanning orchestration (SPEC-batch).

NFR-6.1: Dedicated module, separate from cli.py.
NFR-6.2: Wraps the existing single-URL pipeline — does not replace it.
NFR-6.3: Only depends on existing botaudit modules + stdlib.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TextIO

from botaudit.models import Report


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class URLSuccess:
    """A successfully audited URL."""

    url: str
    report: Report


@dataclass
class URLError:
    """A URL that failed during fetching or analysis (FR-5.1)."""

    url: str
    message: str


# Union type for per-URL results (FR-7.2)
URLResult = URLSuccess | URLError


@dataclass
class BatchResult:
    """Aggregate result for a batch run (FR-7.1)."""

    results: list[URLResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        """Total number of unique URLs attempted."""
        return len(self.results)

    @property
    def succeeded(self) -> int:
        """Number of URLs that completed successfully."""
        return sum(1 for r in self.results if isinstance(r, URLSuccess))

    @property
    def failed(self) -> int:
        """Number of URLs that failed."""
        return sum(1 for r in self.results if isinstance(r, URLError))


# ---------------------------------------------------------------------------
# Input parsing — FR-1, FR-2, FR-3
# NFR-5.1: Pure functions, testable without HTTP requests.
# ---------------------------------------------------------------------------

def parse_url_file(source: TextIO) -> list[tuple[int, str]]:
    """Read URLs from a file-like object.

    FR-2.1: One URL per line.
    FR-2.2: Blank lines ignored.
    FR-2.3: Lines starting with '#' are comments.
    FR-2.4: Whitespace stripped.
    FR-2.8: Caller is responsible for opening with UTF-8 encoding.

    Returns a list of (line_number, url_string) tuples. Each entry is a
    non-blank, non-comment line (stripped). Validation is left to the caller
    so it can report line numbers for invalid entries (FR-2.6).
    """
    entries: list[tuple[int, str]] = []
    for lineno, raw_line in enumerate(source, start=1):
        line = raw_line.strip()
        if not line:
            continue  # FR-2.2
        if line.startswith("#"):
            continue  # FR-2.3
        entries.append((lineno, line))
    return entries


def validate_url(url: str) -> str | None:
    """Validate a single URL string.

    FR-2.5: Same rules as CLI positional args (scheme http/https, netloc present).

    Returns the URL if valid, None if invalid.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return url


def collect_urls(
    positional: list[str],
    file_path: str | None = None,
) -> list[str]:
    """Combine positional URLs and file URLs, validate, and deduplicate.

    FR-1.1: Positional args.
    FR-1.2/FR-1.3: --file path or --file - for stdin.
    FR-1.4: Both sources combined.
    FR-3.1: Deduplicate (order-preserving).
    FR-3.2: Case-sensitive, no normalization.
    FR-3.3: Warn to stderr about duplicates.
    FR-2.6: Warn to stderr about invalid lines.
    FR-2.7: Exit code 2 if zero valid URLs after parsing.

    NFR-4.1: Clear error if file doesn't exist / not readable / is directory.
    NFR-4.3: Clear error if file is non-UTF-8.
    """
    urls: list[str] = list(positional)

    # Read from file if provided (FR-1.2 / FR-1.3)
    if file_path is not None:
        try:
            source = open_url_file(file_path)
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)
        except (OSError, UnicodeDecodeError) as exc:
            print(f"Error reading URL file: {exc}", file=sys.stderr)
            sys.exit(2)

        try:
            entries = parse_url_file(source)
        finally:
            if file_path != "-":
                source.close()

        for lineno, candidate in entries:
            if validate_url(candidate) is not None:
                urls.append(candidate)
            else:
                # FR-2.6: warn about invalid lines
                print(
                    f"Warning: skipping invalid URL on line {lineno}: "
                    f"'{candidate}'",
                    file=sys.stderr,
                )

    # FR-3.1 / FR-3.2: Deduplicate, order-preserving, case-sensitive
    seen: set[str] = set()
    unique: list[str] = []
    dup_count = 0
    for url in urls:
        if url in seen:
            dup_count += 1
        else:
            seen.add(url)
            unique.append(url)

    # FR-3.3: warn about duplicates
    if dup_count:
        print(
            f"Note: {dup_count} duplicate URL(s) skipped.",
            file=sys.stderr,
        )

    # FR-2.7: must have at least one valid URL
    if not unique:
        print("Error: no valid URLs to audit.", file=sys.stderr)
        sys.exit(2)

    return unique


def open_url_file(file_path: str) -> TextIO:
    """Open a URL file for reading.

    FR-1.3: '-' means stdin.
    FR-2.8: UTF-8 encoding, handle BOM.
    NFR-4.1: Clear error message if file not found / not readable / is dir.
    NFR-4.3: Clear error message if non-UTF-8.
    """
    if file_path == "-":
        return sys.stdin

    p = Path(file_path)
    if p.is_dir():
        raise FileNotFoundError(f"'{file_path}' is a directory, not a file")
    if not p.exists():
        raise FileNotFoundError(f"File not found: '{file_path}'")
    # FR-2.8 / NFR-4.3: UTF-8 with BOM handling
    return open(p, encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# Execution — FR-4, FR-5
# NFR-5.2: audit_fn is injectable for testing.
# ---------------------------------------------------------------------------

# Type alias for the single-URL audit function.
# Accepts a URL and keyword args; returns a Report on success, raises on failure.
AuditFn = Callable[..., Report]


def audit_one(
    url: str,
    *,
    timeout: float,
    skip_llm_discovery: bool,
    no_recommendations: bool,
) -> URLResult:
    """Run the full single-URL pipeline and return a URLResult.

    FR-4.1: Full independent audit (fetch -> analyze -> grade -> recommend).
    FR-5.1: Catches FetchError, returns URLError instead of raising.
    """
    from botaudit.analysis import analyze
    from botaudit.fetcher import FetchError, fetch
    from botaudit.grading import grade
    from botaudit.recommendations import recommend

    try:
        html = fetch(url, timeout=timeout)
    except FetchError as exc:
        return URLError(url=url, message=str(exc))

    analysis = analyze(html)

    if not skip_llm_discovery:
        from botaudit.llm_discoverability import (
            analyze_llm_discovery,
            fetch_discovery_files,
        )

        robots_txt, llms_txt, llms_full_txt = fetch_discovery_files(
            url, timeout=timeout
        )
        analysis.llm_discovery = analyze_llm_discovery(
            robots_txt, llms_txt, llms_full_txt
        )

    report = grade(analysis, url)
    if not no_recommendations:
        report.categories = recommend(analysis, report.categories)

    return URLSuccess(url=url, report=report)


def run_batch(
    urls: list[str],
    *,
    audit_fn: AuditFn | None = None,
    timeout: float = 10.0,
    skip_llm_discovery: bool = False,
    no_recommendations: bool = False,
    quiet: bool = False,
) -> BatchResult:
    """Process all URLs sequentially and return aggregate results.

    FR-4.2: Sequential, in order.
    FR-5.1/FR-5.2: Errors logged to stderr, batch continues.
    FR-10.1: Progress to stderr unless quiet.
    FR-10.2: Progress on stderr only.
    NFR-2.1: No artificial delays.
    NFR-3.2: Warn if batch > 100 URLs.

    If audit_fn is None, uses audit_one as the default (NFR-5.2).
    """
    total = len(urls)

    # NFR-3.2: warn on large batches
    if total > 100 and not quiet:
        print(
            f"Warning: {total} URLs to audit — this may take a while.",
            file=sys.stderr,
        )

    results: list[URLResult] = []
    for idx, url in enumerate(urls, start=1):
        # FR-10.1 / FR-10.2: progress to stderr
        if not quiet:
            print(f"[{idx}/{total}] Auditing {url}...", file=sys.stderr)

        if audit_fn is not None:
            # NFR-5.2: injectable audit function for testing
            try:
                report = audit_fn(
                    url,
                    timeout=timeout,
                    skip_llm_discovery=skip_llm_discovery,
                    no_recommendations=no_recommendations,
                )
                results.append(URLSuccess(url=url, report=report))
            except Exception as exc:
                results.append(URLError(url=url, message=str(exc)))
                print(f"  Error: {exc}", file=sys.stderr)
        else:
            result = audit_one(
                url,
                timeout=timeout,
                skip_llm_discovery=skip_llm_discovery,
                no_recommendations=no_recommendations,
            )
            results.append(result)
            if isinstance(result, URLError):
                print(f"  Error: {result.message}", file=sys.stderr)

    return BatchResult(results=results)


# ---------------------------------------------------------------------------
# Output formatting — FR-6, FR-7, FR-8
# NFR-5.3: Testable independently with constructed BatchResult objects.
# ---------------------------------------------------------------------------

def format_batch_text(
    batch: BatchResult,
    *,
    show_recommendations: bool = True,
) -> str:
    """Format batch results as plain text with per-URL reports + summary table.

    FR-6.1: One complete report per URL.
    FR-6.2: Separator between reports.
    FR-6.3–FR-6.6: Summary table at end.
    """
    from botaudit.report import format_report

    sections: list[str] = []
    sep = "=" * 50

    for result in batch.results:
        if isinstance(result, URLSuccess):
            sections.append(
                format_report(result.report, show_recommendations=show_recommendations)
            )
        else:
            # FR-5.3 / FR-6.6: error indicator in individual output
            lines = [
                sep,
                f"  BotAudit Report",
                f"  {result.url}",
                sep,
                "",
                f"  Error: {result.message}",
                "",
            ]
            sections.append("\n".join(lines))

    # FR-6.2: separate reports with blank line + separator
    report_text = f"\n{sep}\n\n".join(sections)

    # FR-6.3–FR-6.6: summary table
    summary = format_summary_table(batch)

    return f"{report_text}\n\n{summary}"


def format_summary_table(batch: BatchResult) -> str:
    """Format the batch summary table.

    FR-6.3: Columns — URL, Grade, Score.
    FR-6.4: Header line with count.
    FR-6.5: One row per URL in order.
    FR-6.6: Failed URLs show ERR / — / reason.
    """
    lines: list[str] = []
    sep = "=" * 50

    lines.append(sep)
    lines.append(f"  Batch Summary ({batch.total} URLs)")
    lines.append(sep)
    lines.append("")
    lines.append(f"  {'URL':<36s} {'Grade':>5s} {'Score':>7s}")
    lines.append(f"  {'-' * 36} {'-' * 5} {'-' * 7}")

    for result in batch.results:
        if isinstance(result, URLSuccess):
            r = result.report
            lines.append(
                f"  {result.url:<36s} {r.grade:>5s} "
                f"{r.overall_score:>5.0f}/100"
            )
        else:
            lines.append(
                f"  {result.url:<36s} {'ERR':>5s} {'—':>7s}"
            )
            lines.append(f"    {result.message}")

    lines.append("")
    return "\n".join(lines)


def format_batch_json(
    batch: BatchResult,
    *,
    show_recommendations: bool = True,
    crawl_result: object | None = None,
) -> str:
    """Format batch results as JSON.

    FR-7.1: Top-level object with batch, total, succeeded, failed, results.
    FR-7.2: Each result is success or error object.
    FR-7.3: Success objects match single-URL JSON structure.
    FR-7.4: Error objects have url, error: true, message.
    SPEC-crawl FR-7.2: Include crawl metadata when present.
    """
    import json

    from botaudit.models import CATEGORY_WEIGHTS

    result_items: list[dict] = []
    for result in batch.results:
        if isinstance(result, URLSuccess):
            r = result.report
            entry: dict = {
                "url": r.url,
                "overall_score": r.overall_score,
                "grade": r.grade,
                "categories": [],
            }
            for cat in r.categories:
                cat_entry: dict = {
                    "name": cat.name,
                    "score": cat.score,
                    "weight": CATEGORY_WEIGHTS.get(cat.name, 0.0),
                    "findings": cat.findings,
                }
                if show_recommendations and cat.recommendations:
                    cat_entry["recommendations"] = [
                        {"message": rec.message, "severity": rec.severity.value}
                        for rec in cat.recommendations
                    ]
                entry["categories"].append(cat_entry)
            result_items.append(entry)
        else:
            result_items.append({
                "url": result.url,
                "error": True,
                "message": result.message,
            })

    data: dict = {
        "batch": True,
        "total": batch.total,
        "succeeded": batch.succeeded,
        "failed": batch.failed,
        "results": result_items,
    }

    # SPEC-crawl FR-7.2: include crawl metadata when present
    if crawl_result is not None:
        from dataclasses import asdict
        data["crawl"] = asdict(crawl_result)

    return json.dumps(data, indent=2)


def format_batch_csv(
    batch: BatchResult,
    *,
    show_recommendations: bool = True,
) -> str:
    """Format batch results as CSV.

    FR-8.1: One header row, then data rows for all URLs.
    FR-8.2: Success rows match single-URL CSV structure.
    FR-8.3: Failed URLs get a single error row.
    FR-8.4: Header appears exactly once.
    """
    import csv
    import io

    from botaudit.models import CATEGORY_WEIGHTS

    buf = io.StringIO()
    writer = csv.writer(buf)

    # FR-8.4: single header row
    header = ["url", "overall_score", "grade", "category", "score", "weight", "findings"]
    if show_recommendations:
        header.append("recommendations")
    writer.writerow(header)

    for result in batch.results:
        if isinstance(result, URLSuccess):
            r = result.report
            for cat in r.categories:
                row: list = [
                    r.url,
                    r.overall_score,
                    r.grade,
                    cat.name,
                    cat.score,
                    CATEGORY_WEIGHTS.get(cat.name, 0.0),
                    "; ".join(cat.findings),
                ]
                if show_recommendations:
                    recs = "; ".join(
                        f"[{rec.severity.value.upper()}] {rec.message}"
                        for rec in cat.recommendations
                    )
                    row.append(recs)
                writer.writerow(row)
        else:
            # FR-8.3: single error row
            row = [result.url, 0, "ERR", "error", 0, 0, result.message]
            if show_recommendations:
                row.append("")
            writer.writerow(row)

    return buf.getvalue().rstrip()


# ---------------------------------------------------------------------------
# Exit code — FR-9
# ---------------------------------------------------------------------------

def determine_exit_code(
    batch: BatchResult,
    fail_under: str | None = None,
) -> int:
    """Compute the process exit code for a batch run.

    FR-9.1: 0 if at least one success and no --fail-under violation.
    FR-9.2: 1 if all URLs failed.
    FR-9.3: 1 if any success grade < fail_under.
    FR-9.4: Failed URLs not evaluated against --fail-under.
    FR-9.5: 1 if --fail-under set and all URLs failed.
    """
    from botaudit.models import GRADE_THRESHOLDS

    # FR-9.2 / FR-9.5: all failed
    if batch.succeeded == 0:
        return 1

    # FR-9.3 / FR-9.4: check --fail-under against successes only
    if fail_under is not None:
        grade_order = {letter: score for score, letter in GRADE_THRESHOLDS}
        threshold = grade_order[fail_under]
        for result in batch.results:
            if isinstance(result, URLSuccess):
                if grade_order[result.report.grade] < threshold:
                    return 1

    # FR-9.1: at least one success, no violations
    return 0
