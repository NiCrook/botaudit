"""Report formatters for botaudit (Spec §5).

5.1  Print results to stdout.
5.2  Display the overall letter grade.
5.3  Display each category's score and a brief summary of findings.
5.5  Clear formatting (headers, indentation) for scannability.

Supports text, JSON, and CSV output formats.
"""

import csv
import html as html_mod
import io
import json
from datetime import datetime, timezone

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


# ---------------------------------------------------------------------------
# HTML formatter — SPEC-html-report
# ---------------------------------------------------------------------------

_GRADE_COLORS: dict[str, str] = {
    "A": "#22c55e",
    "B": "#3b82f6",
    "C": "#eab308",
    "D": "#f97316",
    "F": "#ef4444",
}


def _grade_color(grade: str) -> str:
    """Return the hex color for a letter grade (FR-3.1)."""
    return _GRADE_COLORS.get(grade[0], "#6b7280")


def _score_color(score: float) -> str:
    """Return a color for a numeric score using the same grade scale (FR-3.2)."""
    if score >= 90:
        return _GRADE_COLORS["A"]
    if score >= 80:
        return _GRADE_COLORS["B"]
    if score >= 70:
        return _GRADE_COLORS["C"]
    if score >= 60:
        return _GRADE_COLORS["D"]
    return _GRADE_COLORS["F"]


def _esc(text: str) -> str:
    """HTML-escape user content (NFR-3.2)."""
    return html_mod.escape(text)


def _render_grade_badge(grade: str, score: float) -> str:
    """Render the prominent grade badge (FR-2.1)."""
    color = _grade_color(grade)
    return (
        f'<div class="grade-badge" aria-label="Overall grade: {_esc(grade)}" '
        f'style="background:{color}">'
        f'<span class="grade-letter">{_esc(grade)}</span>'
        f'<span class="grade-score">{score:.0f}/100</span>'
        f'</div>'
    )


def _render_category_card(cat, *, show_recommendations: bool) -> str:
    """Render a single category card (FR-2.1)."""
    weight = CATEGORY_WEIGHTS.get(cat.name, 0.0)
    color = _score_color(cat.score)
    lines = [
        f'<section class="category-card">',
        f'<div class="category-header">',
        f'<h3>{_esc(cat.name)} <span class="weight">({weight * 100:.0f}%)</span></h3>',
        f'<span class="category-score" style="color:{color}">{cat.score:.0f}/100</span>',
        f'</div>',
    ]
    if cat.findings:
        lines.append('<ul class="findings">')
        for finding in cat.findings:
            lines.append(f"<li>{_esc(finding)}</li>")
        lines.append("</ul>")
    if show_recommendations and cat.recommendations:
        lines.append('<div class="recommendations">')
        lines.append("<h4>Recommendations</h4>")
        lines.append("<ul>")
        for rec in cat.recommendations:
            tag = rec.severity.value.upper()
            lines.append(
                f'<li><span class="severity severity-{rec.severity.value}">'
                f"[{tag}]</span> {_esc(rec.message)}</li>"
            )
        lines.append("</ul>")
        lines.append("</div>")
    lines.append("</section>")
    return "\n".join(lines)


def _render_footer() -> str:
    """Render the report footer with timestamp and version (FR-2.1)."""
    from importlib.metadata import version

    try:
        ver = version("botaudit")
    except Exception:
        ver = "unknown"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f'<footer>Generated by BotAudit v{_esc(ver)} on {ts}</footer>'
    )


def _html_document(title: str, body: str) -> str:
    """Wrap body content in a full HTML5 document (FR-6)."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>
{_CSS}
</style>
</head>
<body>
<main>
{body}
</main>
<script>
{_JS}
</script>
</body>
</html>"""


_CSS = """\
*,*::before,*::after{box-sizing:border-box}
body{
  margin:0;padding:2rem;
  font-family:system-ui,-apple-system,sans-serif;
  line-height:1.6;color:#1f2937;background:#f9fafb;
}
main{max-width:900px;margin:0 auto}
a{color:#3b82f6}
header{text-align:center;margin-bottom:2rem}
header h1{margin:0 0 .25rem;font-size:1.5rem}
header .url{color:#6b7280;word-break:break-all}
.grade-badge{
  display:inline-flex;flex-direction:column;align-items:center;
  padding:1rem 2rem;border-radius:1rem;color:#fff;margin:1rem 0;
}
.grade-letter{font-size:3rem;font-weight:700;line-height:1}
.grade-score{font-size:1rem;opacity:.9}
.category-card{
  background:#fff;border:1px solid #e5e7eb;border-radius:.5rem;
  padding:1rem 1.25rem;margin-bottom:1rem;
}
.category-header{display:flex;justify-content:space-between;align-items:center}
.category-header h3{margin:0;font-size:1.1rem}
.weight{color:#9ca3af;font-weight:400;font-size:.9rem}
.category-score{font-size:1.25rem;font-weight:700}
.findings{margin:.5rem 0 0;padding-left:1.25rem}
.findings li{margin-bottom:.25rem}
.recommendations{margin-top:.75rem;padding-top:.75rem;border-top:1px solid #f3f4f6}
.recommendations h4{margin:0 0 .25rem;font-size:.95rem;color:#6b7280}
.recommendations ul{padding-left:1.25rem;margin:0}
.recommendations li{margin-bottom:.25rem}
.severity{font-weight:600;font-size:.8rem;margin-right:.25rem}
.severity-high{color:#ef4444}
.severity-medium{color:#f97316}
.severity-low{color:#3b82f6}
footer{text-align:center;color:#9ca3af;font-size:.85rem;margin-top:2rem;padding-top:1rem;border-top:1px solid #e5e7eb}

/* Batch mode */
.batch-summary{margin-bottom:2rem}
.summary-table{width:100%;border-collapse:collapse;margin-top:1rem}
.summary-table th,.summary-table td{text-align:left;padding:.5rem .75rem;border-bottom:1px solid #e5e7eb}
.summary-table th{cursor:pointer;user-select:none;background:#f9fafb;font-size:.85rem;text-transform:uppercase;color:#6b7280}
.summary-table th:hover{background:#f3f4f6}
.summary-table .err{color:#ef4444}
.summary-table a{text-decoration:none}
.summary-table a:hover{text-decoration:underline}
details.url-detail{background:#fff;border:1px solid #e5e7eb;border-radius:.5rem;margin-bottom:1rem}
details.url-detail summary{padding:1rem 1.25rem;cursor:pointer;font-weight:600;list-style:none}
details.url-detail summary::-webkit-details-marker{display:none}
details.url-detail summary::before{content:"\\25B6";display:inline-block;margin-right:.5rem;transition:transform .2s}
details.url-detail[open] summary::before{transform:rotate(90deg)}
.detail-body{padding:0 1.25rem 1rem}
.controls{margin-bottom:1rem}
.controls button{
  background:#fff;border:1px solid #d1d5db;border-radius:.375rem;
  padding:.375rem .75rem;cursor:pointer;font-size:.85rem;margin-right:.5rem;
}
.controls button:hover{background:#f3f4f6}
.crawl-meta{background:#eff6ff;border:1px solid #bfdbfe;border-radius:.5rem;padding:.75rem 1rem;margin-bottom:1rem;font-size:.9rem}

/* Dark mode (FR-7.3) */
@media(prefers-color-scheme:dark){
  body{background:#111827;color:#f3f4f6}
  .category-card,details.url-detail{background:#1f2937;border-color:#374151}
  .summary-table th{background:#1f2937;color:#9ca3af}
  .summary-table th:hover{background:#374151}
  .summary-table td{border-color:#374151}
  .recommendations{border-color:#374151}
  footer{border-color:#374151;color:#6b7280}
  .controls button{background:#1f2937;border-color:#374151;color:#f3f4f6}
  .controls button:hover{background:#374151}
  .crawl-meta{background:#1e3a5f;border-color:#2563eb}
}
"""

_JS = """\
document.addEventListener('DOMContentLoaded',function(){
  // Column sorting for summary table (FR-4.1)
  document.querySelectorAll('.summary-table th[data-sort]').forEach(function(th){
    th.addEventListener('click',function(){
      var table=th.closest('table'),tbody=table.querySelector('tbody');
      var idx=Array.from(th.parentNode.children).indexOf(th);
      var rows=Array.from(tbody.querySelectorAll('tr'));
      var asc=th.dataset.asc!=='true';
      th.dataset.asc=asc;
      rows.sort(function(a,b){
        var av=a.children[idx].dataset.value||a.children[idx].textContent;
        var bv=b.children[idx].dataset.value||b.children[idx].textContent;
        var an=parseFloat(av),bn=parseFloat(bv);
        if(!isNaN(an)&&!isNaN(bn))return asc?an-bn:bn-an;
        return asc?av.localeCompare(bv):bv.localeCompare(av);
      });
      rows.forEach(function(r){tbody.appendChild(r)});
    });
  });
  // Expand / Collapse all (FR-4.6)
  var expandBtn=document.getElementById('expand-all');
  var collapseBtn=document.getElementById('collapse-all');
  if(expandBtn){
    expandBtn.addEventListener('click',function(){
      document.querySelectorAll('details.url-detail').forEach(function(d){d.open=true});
    });
  }
  if(collapseBtn){
    collapseBtn.addEventListener('click',function(){
      document.querySelectorAll('details.url-detail').forEach(function(d){d.open=false});
    });
  }
});
"""


def format_html(report: Report, *, show_recommendations: bool = True) -> str:
    """Return *report* as a self-contained HTML document (SPEC-html-report FR-9.1)."""
    parts: list[str] = []

    # Header (FR-2.1)
    parts.append("<header>")
    parts.append("<h1>BotAudit Report</h1>")
    parts.append(
        f'<p class="url"><a href="{_esc(report.url)}">{_esc(report.url)}</a></p>'
    )
    parts.append(_render_grade_badge(report.grade, report.overall_score))
    parts.append("</header>")

    # Category breakdown (FR-2.1)
    for cat in report.categories:
        parts.append(
            _render_category_card(cat, show_recommendations=show_recommendations)
        )

    # Footer (FR-2.1)
    parts.append(_render_footer())

    title = f"BotAudit Report \u2014 {report.url}"
    return _html_document(title, "\n".join(parts))
