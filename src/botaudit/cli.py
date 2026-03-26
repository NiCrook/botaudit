import argparse
import sys
from urllib.parse import urlparse

from botaudit.fetcher import DEFAULT_TIMEOUT, FetchError, fetch


def validate_url(url: str) -> str:
    """Validate that a string is a well-formed HTTP(S) URL.

    Returns the URL if valid, raises argparse.ArgumentTypeError otherwise.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise argparse.ArgumentTypeError(
            f"Invalid URL '{url}': scheme must be http or https"
        )
    if not parsed.netloc:
        raise argparse.ArgumentTypeError(
            f"Invalid URL '{url}': missing domain"
        )
    return url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="botaudit",
        description="Grade how accessible a website is to AI clients.",
    )
    parser.add_argument(
        "urls",
        nargs="*",
        type=validate_url,
        metavar="URL",
        help="URL(s) to analyze (must be http or https)",
    )
    parser.add_argument(
        "-f", "--file",
        default=None,
        dest="file",
        metavar="FILE",
        help="File containing URLs to audit (one per line; use '-' for stdin)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--no-recommendations",
        action="store_true",
        default=False,
        help="Suppress improvement recommendations in output",
    )
    parser.add_argument(
        "--skip-llm-discovery",
        action="store_true",
        default=False,
        help="Skip LLM discoverability analysis (no robots.txt/llms.txt fetches)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--fail-under",
        choices=["A", "B", "C", "D", "F"],
        default=None,
        metavar="GRADE",
        help="Exit with code 1 if overall grade is below GRADE (e.g. --fail-under B)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        default=False,
        help="Suppress progress messages in batch mode",
    )
    return parser


# -----------------------------------------------------------------------
# Single-URL path — NFR-6.2: unchanged from original
# -----------------------------------------------------------------------

def _run_single(args: argparse.Namespace) -> None:
    """Original single-URL pipeline. Kept intact for NFR-1.1 compatibility."""
    url = args.urls[0]

    try:
        html = fetch(url, timeout=args.timeout)
    except FetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    from botaudit.analysis import analyze
    from botaudit.grading import grade
    from botaudit.recommendations import recommend
    from botaudit.report import print_report

    analysis = analyze(html)

    if not args.skip_llm_discovery:
        from botaudit.llm_discoverability import (
            analyze_llm_discovery,
            fetch_discovery_files,
        )

        robots_txt, llms_txt, llms_full_txt = fetch_discovery_files(
            url, timeout=args.timeout
        )
        analysis.llm_discovery = analyze_llm_discovery(
            robots_txt, llms_txt, llms_full_txt
        )

    report = grade(analysis, url)
    show_recs = not args.no_recommendations
    if show_recs:
        report.categories = recommend(analysis, report.categories)

    if args.output_format == "json":
        from botaudit.report import format_json
        print(format_json(report, show_recommendations=show_recs))
    elif args.output_format == "csv":
        from botaudit.report import format_csv
        print(format_csv(report, show_recommendations=show_recs))
    else:
        print_report(report, show_recommendations=show_recs)

    if args.fail_under is not None:
        from botaudit.models import GRADE_THRESHOLDS
        grade_order = {letter: score for score, letter in GRADE_THRESHOLDS}
        if grade_order[report.grade] < grade_order[args.fail_under]:
            sys.exit(1)


# -----------------------------------------------------------------------
# Batch path — FR-1 through FR-10
# -----------------------------------------------------------------------

def _run_batch(args: argparse.Namespace, urls: list[str]) -> None:
    """Batch pipeline: multiple URLs via batch module."""
    from botaudit.batch import (
        determine_exit_code,
        format_batch_csv,
        format_batch_json,
        format_batch_text,
        run_batch,
    )

    batch = run_batch(
        urls,
        timeout=args.timeout,
        skip_llm_discovery=args.skip_llm_discovery,
        no_recommendations=args.no_recommendations,
        quiet=args.quiet,
    )

    show_recs = not args.no_recommendations

    if args.output_format == "json":
        print(format_batch_json(batch, show_recommendations=show_recs))
    elif args.output_format == "csv":
        print(format_batch_csv(batch, show_recommendations=show_recs))
    else:
        print(format_batch_text(batch, show_recommendations=show_recs))

    exit_code = determine_exit_code(batch, fail_under=args.fail_under)
    if exit_code != 0:
        sys.exit(exit_code)


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # FR-1.5: need at least one URL from positional or --file
    if not args.urls and args.file is None:
        parser.error("the following arguments are required: URL (or --file)")

    # FR-1.4: collect all URLs (positional + file), validate, deduplicate
    from botaudit.batch import collect_urls
    urls = collect_urls(args.urls, file_path=args.file)

    # FR-1.6 / NFR-1.1: single URL = original code path
    if len(urls) == 1 and args.file is None:
        args.urls = urls
        _run_single(args)
    else:
        _run_batch(args, urls)


if __name__ == "__main__":
    main()
