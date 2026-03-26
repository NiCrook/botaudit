# ADR-001: HTML Parser Selection

## Status

Accepted

## Context

AI-508 needs to parse raw HTML responses from arbitrary websites and perform structural analysis (counting elements by type, extracting text content, finding meta tags, etc.). Real-world HTML is frequently malformed, so the parser must be tolerant of broken markup.

## Options Considered

### 1. BeautifulSoup4 with html.parser backend
- Pure Python, no C dependencies
- Friendly API for navigating and querying the DOM
- Handles malformed HTML gracefully
- Widely adopted, well-documented
- Moderate performance (sufficient for single-page analysis)

### 2. lxml
- Fast (C-based)
- XPath support
- Requires C library installation, which can be problematic on some systems
- Less forgiving with badly formed HTML unless used via BeautifulSoup

### 3. html.parser (stdlib only)
- Zero dependencies
- Limited querying API — no CSS selectors, no easy tree traversal
- More fragile with malformed HTML
- Would require significant wrapper code to match BS4's ergonomics

## Decision

**BeautifulSoup4 with html.parser as its parser backend.**

This gives us BS4's querying API and tolerance for malformed HTML without introducing a C dependency. Since the MVP analyzes a single page per invocation, performance is not a bottleneck. If it becomes one later, we can swap in lxml as the backend with no API changes — BS4 abstracts the parser behind the same interface.

## Consequences

- One external dependency (beautifulsoup4) beyond httpx
- Slightly slower than lxml for large documents, acceptable for MVP
- Easy migration path to lxml if needed — change one argument in the BS4 constructor
