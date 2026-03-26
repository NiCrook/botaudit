# AI-508: AI Accessibility Grader — MVP

## Concept

A CLI tool that evaluates how accessible a website is to AI clients (LLMs, agents, scrapers) by analyzing the raw HTML response — no JavaScript execution. Inspired by Section 508 compliance for human accessibility, applied to machine consumers.

## Functional Requirements

1. **URL Input** — accepts a single URL as a command-line argument
2. **Raw HTML Fetch** — performs a standard HTTP GET, no JS execution (this is what an AI client actually sees)
3. **Analysis Categories:**
   - **Semantic HTML** — ratio of semantic elements (`<nav>`, `<main>`, `<article>`, `<section>`, `<header>`, `<footer>`, `<table>`, `<form>`, `<ul>`, `<ol>`) vs generic containers (`<div>`, `<span>`)
   - **Content Availability** — is there meaningful text in the raw HTML, or is it an empty shell waiting on JS to render?
   - **Link Discoverability** — presence of real `<a href>` tags with navigable URLs
   - **Structured Data** — JSON-LD blocks, Open Graph tags, meta descriptions
   - **Metadata / Discoverability** — `<title>`, robots.txt reference, sitemap reference, meta tags
4. **Letter Grade Output** — overall A–F grade with per-category breakdown and brief reasoning

## Non-Functional Requirements

1. **No browser dependency** — no Puppeteer, Playwright, or Selenium. Raw HTTP only.
2. **Fast** — single fetch + parse, results in seconds
3. **Minimal dependencies** — Python, httpx, BeautifulSoup (or lxml)
4. **Readable output** — clear terminal output a human can act on without docs

## Out of Scope

- JS-rendered comparison / delta scoring
- Multi-page crawling
- TUI or web interface
- PDF or HTML reports
- API mode
- LLM-based analysis

## Tech Stack

- Python 3.11+
- httpx (HTTP client)
- BeautifulSoup4 (HTML parsing)
- CLI via argparse

## Grading Scale

| Grade | Meaning |
|-------|---------|
| A | Highly accessible to AI clients — semantic, content-rich, well-structured |
| B | Good — mostly accessible with minor gaps |
| C | Fair — some content available but significant reliance on JS or poor structure |
| D | Poor — minimal useful content in raw HTML |
| F | Inaccessible — empty shell, no meaningful content without JS execution |
