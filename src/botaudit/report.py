"""Report formatters for botaudit (Spec §5).

5.1  Print results to stdout.
5.2  Display the overall letter grade.
5.3  Display each category's score and a brief summary of findings.
5.5  Clear formatting (headers, indentation) for scannability.

Supports text, JSON, and CSV output formats.
"""

import csv
import io
import json

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


def format_json(report: Report, *, show_recommendations: bool = True) -> str:
    """Return *report* as a JSON string."""
    data = {
        "url": report.url,
        "overall_score": report.overall_score,
        "grade": report.grade,
        "categories": [],
    }
    for cat in report.categories:
        entry = {
            "name": cat.name,
            "score": cat.score,
            "weight": CATEGORY_WEIGHTS.get(cat.name, 0.0),
            "findings": cat.findings,
        }
        if show_recommendations and cat.recommendations:
            entry["recommendations"] = [
                {"message": r.message, "severity": r.severity.value}
                for r in cat.recommendations
            ]
        data["categories"].append(entry)
    return json.dumps(data, indent=2)


def format_csv(report: Report, *, show_recommendations: bool = True) -> str:
    """Return *report* as a CSV string with one row per category."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ["url", "overall_score", "grade", "category", "score", "weight", "findings"]
    if show_recommendations:
        header.append("recommendations")
    writer.writerow(header)
    for cat in report.categories:
        row = [
            report.url,
            report.overall_score,
            report.grade,
            cat.name,
            cat.score,
            CATEGORY_WEIGHTS.get(cat.name, 0.0),
            "; ".join(cat.findings),
        ]
        if show_recommendations:
            recs = "; ".join(
                f"[{r.severity.value.upper()}] {r.message}"
                for r in cat.recommendations
            )
            row.append(recs)
        writer.writerow(row)
    return buf.getvalue().rstrip()


def print_report(report: Report, *, show_recommendations: bool = True) -> None:
    """Format and print *report* to stdout."""
    print(format_report(report, show_recommendations=show_recommendations))
