# botaudit

[![PyPI](https://img.shields.io/pypi/v/botaudit)](https://pypi.org/project/botaudit/)
[![Python](https://img.shields.io/pypi/pyversions/botaudit)](https://pypi.org/project/botaudit/)
[![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-blue)](LICENSE.md)
[![Version](https://img.shields.io/badge/version-1.3.0-green)](https://github.com/NiCrook/botaudit/releases/tag/v1.3.0)

CLI tool that grades how accessible a website is to AI clients.

botaudit fetches a webpage, analyzes its HTML structure, and scores it across six categories that affect how well AI crawlers and language models can discover and consume its content. The output is a letter-graded report with per-category scores and actionable recommendations.

## Installation

Requires Python 3.11+.

```bash
pip install botaudit
```

## Usage

```bash
# Single URL
botaudit https://example.com

# Multiple URLs
botaudit https://example.com https://example.org

# Batch from file
botaudit --file urls.txt

# Crawl a site via sitemap
botaudit --crawl https://example.com

# HTML report
botaudit https://example.com --format html > report.html
```

### Options

| Flag | Description |
|---|---|
| `--format {text,json,csv,html}` | Output format (default: text) |
| `--timeout SECONDS` | HTTP request timeout (default: 10) |
| `--fail-under GRADE` | Exit with code 1 if grade is below GRADE (A–F) |
| `--no-recommendations` | Suppress improvement recommendations |
| `--skip-llm-discovery` | Skip LLM discoverability analysis |
| `-q`, `--quiet` | Suppress progress messages |
| `--file`, `-f` | Read URLs from a file (one per line, `#` comments supported) |
| `--crawl URL` | Discover and audit pages from XML sitemaps |
| `--crawl-limit`, `-l` | Cap the number of crawl-discovered URLs |
| `--crawl-allow-external` | Allow crawling URLs outside the origin domain |
| `--weight-profile PROFILE` | Use a built-in weight preset (`ecommerce`, `docs`, `ai-ready`) |
| `--weight`, `-w` | Override a category weight (e.g., `-w structured=0.2`) |
| `--list-profiles` | Display available weight profiles |
| `--page-type TYPE` | Force a specific page type (article, product, documentation, listing, homepage) |
| `--no-page-type` | Disable page-type detection |
| `--config PATH` | Load config from a specific file (`--config none` to disable) |

### Configuration file

botaudit supports project-level configuration via `.botaudit.yaml` or `[tool.botaudit]` in `pyproject.toml`. CLI flags always take precedence.

```yaml
# .botaudit.yaml
format: json
timeout: 15
fail_under: B
weight_profile: ai-ready
weights:
  llm: 0.2
```

### CI usage

```bash
# Fail the build if the site scores below a B
botaudit https://staging.myapp.com --fail-under B --format json
```

### Library mode

```python
from botaudit import audit, audit_batch

# Single URL
report = audit("https://example.com")
print(report.overall_grade, report.overall_score)

# Multiple URLs
result = audit_batch(["https://example.com", "https://example.org"])
for url, report in result.reports.items():
    print(url, report.overall_grade)
```

### Example output

```
==================================================
  BotAudit Report
  https://example.com
==================================================

  Page type: homepage (medium confidence)
  Overall Grade: B (82/100)

--------------------------------------------------
  Content Availability (27%)              90/100
--------------------------------------------------
    - 342 words of visible text.
    - <noscript> fallback present.

  Semantic HTML (23%)                     68/100
--------------------------------------------------
    - 15 semantic vs 7 generic elements (ratio: 68%)
    - Semantic tags: nav (3), article (2), section (4), header (2), ...

    Recommendations:
    [MEDIUM] Wrap supplementary content (sidebars, promos) with <aside>.
    ...
```

## Categories

Each category is scored 0-100 and weighted toward the overall grade:

| Category | Weight | What it measures |
|---|---|---|
| Content Availability | 27% | Visible text in initial HTML, `<noscript>` fallback |
| Semantic HTML | 23% | Ratio of semantic elements (`<article>`, `<nav>`, ...) to generic containers (`<div>`, `<span>`) |
| Link Discoverability | 18% | Navigable `<a href>` links vs `javascript:`, `#`, or empty hrefs |
| Structured Data | 13% | JSON-LD parsing & validation, Open Graph, meta description quality, Twitter Cards, Microdata |
| Metadata & Discoverability | 9% | `<title>`, canonical URL, robots meta, sitemap reference |
| LLM Discoverability | 10% | robots.txt AI crawler policies, llms.txt, llms-full.txt, ai.txt, ai-plugin.json, agent.json |

Grades map to the overall weighted score: A (90+), B (80-89), C (70-79), D (60-69), F (<60).

Category weights can be customized with `--weight-profile` or `--weight` overrides.

Page-type detection (article, product, documentation, listing, homepage) provides type-aware recommendations tailored to each page's purpose.

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

### Running tests

```bash
python -m pytest tests/
```

### Project structure

```
src/botaudit/
  __init__.py            Public API exports
  api.py                 Library mode (audit, audit_batch)
  cli.py                 CLI entry point and argument parsing
  config.py              Configuration file loading and validation
  fetcher.py             HTTP fetching with OS trust store support
  analysis.py            HTML analysis (5 categories)
  robots_analysis.py     robots.txt parsing for AI crawler access
  llm_discoverability.py LLM discovery file fetching and analysis
  grading.py             Per-category scoring and overall grading
  page_type.py           Page-type heuristic detection
  recommendations.py     Per-category recommendation generation
  report.py              Report formatting (text, JSON, CSV, HTML)
  batch.py               Batch and crawl orchestration
  crawl.py               Sitemap discovery and parsing
  models.py              Shared data structures and constants
```
