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
        "url",
        type=validate_url,
        help="URL to analyze (must be http or https)",
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
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        html = fetch(args.url, timeout=args.timeout)
    except FetchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    from botaudit.analysis import analyze
    from botaudit.grading import grade
    from botaudit.recommendations import recommend
    from botaudit.report import print_report

    analysis = analyze(html)

    # FR-1 / NFR-4.1 — LLM Discoverability fetches (unless skipped)
    if not args.skip_llm_discovery:
        from botaudit.llm_discoverability import (
            analyze_llm_discovery,
            fetch_discovery_files,
        )

        robots_txt, llms_txt, llms_full_txt = fetch_discovery_files(
            args.url, timeout=args.timeout
        )
        analysis.llm_discovery = analyze_llm_discovery(
            robots_txt, llms_txt, llms_full_txt
        )

    report = grade(analysis, args.url)
    show_recs = not args.no_recommendations
    if show_recs:
        report.categories = recommend(analysis, report.categories)
    print_report(report, show_recommendations=show_recs)


if __name__ == "__main__":
    main()
