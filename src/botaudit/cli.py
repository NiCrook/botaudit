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
        choices=["text", "json", "csv", "html"],
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

    # Custom weight flags (SPEC-custom-weights)
    parser.add_argument(
        "-w", "--weight",
        action="append",
        dest="weight_overrides",
        default=None,
        metavar="CATEGORY=VALUE",
        help="Override weight for a category (repeatable). "
             "Value is a decimal (0.30) or percentage (30%%)",
    )
    parser.add_argument(
        "-W", "--weight-profile",
        default=None,
        metavar="PROFILE",
        help="Use a named weight profile as the base weights",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        default=False,
        help="List available weight profiles and exit",
    )

    # Crawl mode flags (SPEC-crawl)
    parser.add_argument(
        "--crawl",
        type=validate_url,
        default=None,
        metavar="URL",
        help="Target origin for sitemap-based URL discovery",
    )
    parser.add_argument(
        "--crawl-limit",
        "-l",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of crawl-discovered URLs to audit",
    )
    parser.add_argument(
        "--crawl-allow-external",
        action="store_true",
        default=False,
        help="Include URLs from sitemaps that point to other origins",
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

    report = grade(analysis, url, weights=args.weights)
    show_recs = not args.no_recommendations
    if show_recs:
        report.categories = recommend(analysis, report.categories)

    if args.output_format == "json":
        from botaudit.report import format_json
        print(format_json(report, show_recommendations=show_recs, weights=args.weights))
    elif args.output_format == "csv":
        from botaudit.report import format_csv
        print(format_csv(report, show_recommendations=show_recs, weights=args.weights))
    elif args.output_format == "html":
        from botaudit.report import format_html
        print(format_html(report, show_recommendations=show_recs, weights=args.weights))
    else:
        print_report(report, show_recommendations=show_recs, weights=args.weights)

    if args.fail_under is not None:
        from botaudit.models import GRADE_THRESHOLDS
        grade_order = {letter: score for score, letter in GRADE_THRESHOLDS}
        if grade_order[report.grade] < grade_order[args.fail_under]:
            sys.exit(1)


# -----------------------------------------------------------------------
# Batch path — FR-1 through FR-10
# -----------------------------------------------------------------------

def _run_batch(
    args: argparse.Namespace,
    urls: list[str],
    crawl_result: object | None = None,
) -> None:
    """Batch pipeline: multiple URLs via batch module."""
    from botaudit.batch import (
        determine_exit_code,
        format_batch_csv,
        format_batch_html,
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
        weights=args.weights,
    )

    show_recs = not args.no_recommendations

    if args.output_format == "json":
        print(format_batch_json(
            batch,
            show_recommendations=show_recs,
            crawl_result=crawl_result,
            weights=args.weights,
        ))
    elif args.output_format == "csv":
        print(format_batch_csv(
            batch,
            show_recommendations=show_recs,
            weights=args.weights,
        ))
    elif args.output_format == "html":
        print(format_batch_html(
            batch,
            show_recommendations=show_recs,
            crawl_result=crawl_result,
            weights=args.weights,
        ))
    else:
        print(format_batch_text(
            batch,
            show_recommendations=show_recs,
            weights=args.weights,
        ))

    exit_code = determine_exit_code(batch, fail_under=args.fail_under)
    if exit_code != 0:
        sys.exit(exit_code)


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    # SPEC-custom-weights FR-5: --list-profiles exits immediately
    if args.list_profiles:
        from botaudit.models import format_profiles
        print(format_profiles())
        return

    # SPEC-custom-weights: resolve weights once at startup (NFR-2.1)
    from botaudit.models import resolve_weights
    try:
        weights = resolve_weights(
            profile=args.weight_profile,
            overrides=args.weight_overrides,
        )
    except ValueError as exc:
        parser.error(str(exc))

    # Attach resolved weights to args so _run_single/_run_batch can access them
    args.weights = weights

    # FR-1.5: need at least one URL from positional, --file, or --crawl
    if not args.urls and args.file is None and args.crawl is None:
        parser.error("the following arguments are required: URL (or --file / --crawl)")

    # NFR-1.2: ignore crawl-specific flags when --crawl not specified
    crawl_urls: list[str] = []
    crawl_result = None
    if args.crawl is not None:
        from botaudit.crawl import crawl
        crawl_urls, crawl_result = crawl(
            args.crawl,
            timeout=args.timeout,
            limit=args.crawl_limit,
            allow_external=args.crawl_allow_external,
            quiet=args.quiet,
        )

    # FR-1.4 / FR-6.1: collect all URLs (positional + crawl + file), validate, deduplicate
    # FR-6.4: crawl URLs appear after positional, before --file
    from botaudit.batch import collect_urls
    combined_positional = list(args.urls or []) + crawl_urls
    urls = collect_urls(combined_positional, file_path=args.file)

    # FR-1.5 / FR-2.4: if crawl was sole source and yielded nothing, exit 2
    if not urls:
        print("Error: no valid URLs to audit.", file=sys.stderr)
        sys.exit(2)

    # FR-6.3 / NFR-1.1: single URL = original code path
    if len(urls) == 1 and args.file is None and args.crawl is None:
        args.urls = urls
        _run_single(args)
    else:
        _run_batch(args, urls, crawl_result=crawl_result)


if __name__ == "__main__":
    main()
