"""Plain-text report formatter for botaudit (Spec §5).

5.1  Print results to stdout.
5.2  Display the overall letter grade.
5.3  Display each category's score and a brief summary of findings.
5.4  Plain text only — no JSON, HTML, or other formats.
5.5  Clear formatting (headers, indentation) for scannability.
"""

from botaudit.models import CATEGORY_WEIGHTS, Report

SEPARATOR = "=" * 50
THIN_SEP = "-" * 50


def format_report(report: Report, *, show_recommendations: bool = True) -> str:
    """Return *report* as a formatted plain-text string."""
    lines: list[str] = []

    # Header
    lines.append(SEPARATOR)
    lines.append(f"  BotAudit Report")
    lines.append(f"  {report.url}")
    lines.append(SEPARATOR)
    lines.append("")

    # Overall grade
    lines.append(
        f"  Overall Grade: {report.grade} ({report.overall_score:.0f}/100)"
    )
    lines.append("")
    lines.append(THIN_SEP)

    # Category breakdown
    for cat in report.categories:
        weight = CATEGORY_WEIGHTS.get(cat.name, 0.0)
        weight_pct = f"{weight * 100:.0f}%"
        label = f"{cat.name} ({weight_pct})"
        score_str = f"{cat.score:.0f}/100"
        lines.append(f"  {label:<36s} {score_str:>7s}")
        lines.append(THIN_SEP)
        for finding in cat.findings:
            lines.append(f"    - {finding}")
        if show_recommendations and cat.recommendations:
            lines.append("")
            lines.append("    Recommendations:")
            for rec in cat.recommendations:
                tag = rec.severity.value.upper()
                lines.append(f"    [{tag}] {rec.message}")
        lines.append("")

    return "\n".join(lines)


def print_report(report: Report, *, show_recommendations: bool = True) -> None:
    """Format and print *report* to stdout."""
    print(format_report(report, show_recommendations=show_recommendations))
