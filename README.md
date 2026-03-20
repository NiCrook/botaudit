# botaudit

CLI tool that grades how accessible a website is to AI clients.

botaudit fetches a webpage, analyzes its HTML structure, and scores it across six categories that affect how well AI crawlers and language models can discover and consume its content. The output is a letter-graded report with per-category scores and actionable recommendations.

## Installation

Requires Python 3.11+.

```bash
pip install .
```

## Usage

```bash
botaudit https://example.com
```

### Options

| Flag | Description |
|---|---|
| `--timeout SECONDS` | HTTP request timeout (default: 10) |
| `--no-recommendations` | Suppress improvement recommendations |
| `--skip-llm-discovery` | Skip LLM discoverability analysis (no robots.txt/llms.txt fetches) |

### Example output

```
==================================================
  BotAudit Report
  https://example.com
==================================================

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
| Structured Data | 13% | JSON-LD, Open Graph tags, meta description |
| Metadata & Discoverability | 9% | `<title>`, canonical URL, robots meta, sitemap reference |
| LLM Discoverability | 10% | robots.txt AI crawler policies, llms.txt, llms-full.txt |

Grades map to the overall weighted score: A (90+), B (80-89), C (70-79), D (60-69), F (<60).

Categories scoring below 90 receive actionable recommendations at HIGH, MEDIUM, or LOW severity.

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .
```

### Running tests

```bash
python -m unittest discover tests
```

### Project structure

```
src/botaudit/
  cli.py                 CLI entry point and argument parsing
  fetcher.py             HTTP fetching with error handling
  analysis.py            HTML analysis (5 categories)
  robots_analysis.py     robots.txt parsing for AI crawler access
  llm_discoverability.py LLM discovery file fetching and analysis
  grading.py             Per-category scoring and overall grading
  recommendations.py     Per-category recommendation generation
  report.py              Plain-text report formatting
  models.py              Shared data structures and constants
```
