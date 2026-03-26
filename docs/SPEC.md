# AI-508 MVP Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in RFC 2119.

---

## 1. Input ✅

> **Status:** Implemented in `src/ai_508/cli.py`

1.1. The tool SHALL accept a single URL as a command-line argument.

1.2. The tool SHALL validate that the input is a well-formed URL before making any request.

1.3. The tool SHALL NOT accept more than one URL per invocation.

1.4. The tool SHOULD provide a clear error message if no URL or an invalid URL is provided.

---

## 2. HTTP Fetching ✅

> **Status:** Implemented in `src/ai_508/fetcher.py`

2.1. The tool SHALL perform a standard HTTP GET request to the provided URL.

2.2. The tool SHALL NOT execute JavaScript or render the page in a browser environment.

2.3. The tool SHALL send a reasonable User-Agent header identifying itself.

2.4. The tool SHALL follow HTTP redirects (up to a reasonable limit).

2.5. The tool SHALL timeout after a configurable duration. The default timeout SHOULD be 10 seconds.

2.6. The tool SHALL handle HTTP errors (4xx, 5xx) gracefully and report them to the user.

2.7. The tool SHALL handle network errors (DNS failure, connection refused, timeout) gracefully and report them to the user.

---

## 3. Analysis ✅

> **Status:** Implemented in `src/ai_508/analysis.py`

### 3.1. Semantic HTML

3.1.1. The tool SHALL count the number of semantic HTML elements present in the document. Semantic elements include: `<nav>`, `<main>`, `<article>`, `<section>`, `<header>`, `<footer>`, `<aside>`, `<table>`, `<form>`, `<ul>`, `<ol>`, `<figure>`, `<figcaption>`, `<details>`, `<summary>`, `<time>`, `<mark>`, `<address>`.

3.1.2. The tool SHALL count the number of generic container elements (`<div>`, `<span>`).

3.1.3. The tool SHALL compute a ratio of semantic elements to total container elements (semantic + generic).

3.1.4. The tool SHALL NOT penalize documents that have few elements overall; the ratio is what matters.

### 3.2. Content Availability

3.2.1. The tool SHALL extract visible text content from the raw HTML response.

3.2.2. The tool SHALL determine whether the document contains meaningful text content or is an empty shell (e.g., a single `<div id="root">` with no text).

3.2.3. The tool SHOULD measure the amount of visible text (e.g., character count or word count) as a signal.

3.2.4. The tool SHALL check for the presence of `<noscript>` content as a fallback indicator.

### 3.3. Link Discoverability

3.3.1. The tool SHALL count the number of `<a>` elements with an `href` attribute.

3.3.2. The tool SHALL distinguish between navigable links (relative or absolute URLs) and non-navigable links (`href="#"`, `href="javascript:..."`, empty `href`).

3.3.3. The tool SHOULD report the ratio of navigable to total links.

### 3.4. Structured Data

3.4.1. The tool SHALL check for the presence of JSON-LD (`<script type="application/ld+json">`).

3.4.2. The tool SHALL check for the presence of Open Graph meta tags (`<meta property="og:...">`).

3.4.3. The tool SHALL check for the presence of a meta description (`<meta name="description">`).

3.4.4. The tool MAY check for other structured data formats (microdata, RDFa) in future versions.

### 3.5. Metadata and Discoverability

3.5.1. The tool SHALL check for the presence of a `<title>` element with non-empty content.

3.5.2. The tool SHALL check for a canonical URL (`<link rel="canonical">`).

3.5.3. The tool SHALL check for a sitemap reference (`<link rel="sitemap">` or in robots.txt).

3.5.4. The tool SHOULD check for a robots meta tag and report its directives.

3.5.5. The tool SHALL NOT make a separate request to robots.txt or sitemap.xml in the MVP. Analysis is limited to what is present in the HTML response.

---

## 4. Grading ✅

> **Status:** Implemented in `src/ai_508/grading.py` and `src/ai_508/models.py`

4.1. The tool SHALL assign a score to each analysis category.

4.2. The tool SHALL compute an overall score from the category scores.

4.3. The tool SHALL map the overall score to a letter grade using the following scale:

| Score Range | Grade |
|-------------|-------|
| 90–100      | A     |
| 80–89       | B     |
| 70–79       | C     |
| 60–69       | D     |
| 0–59        | F     |

4.4. The grading algorithm SHOULD weight categories to reflect their relative importance to AI accessibility. Suggested weights:

| Category                  | Weight |
|---------------------------|--------|
| Content Availability      | 30%    |
| Semantic HTML             | 25%    |
| Link Discoverability      | 20%    |
| Structured Data           | 15%    |
| Metadata / Discoverability| 10%    |

4.5. The tool MAY adjust weights in future versions based on empirical testing.

---

## 5. Output ✅

> **Status:** Implemented in `src/ai_508/models.py` and `src/ai_508/report.py`

5.1. The tool SHALL print results to stdout.

5.2. The tool SHALL display the overall letter grade.

5.3. The tool SHALL display each category's score and a brief summary of findings.

5.4. The tool SHALL NOT produce output in any format other than plain text in the MVP.

5.5. The tool SHOULD use clear formatting (e.g., headers, indentation) to make the output scannable.

---

## 6. Error Handling ✅

> **Status:** Implemented in `src/ai_508/cli.py` and `src/ai_508/fetcher.py`

6.1. The tool SHALL exit with a non-zero exit code on failure (invalid input, network error, HTTP error).

6.2. The tool SHALL exit with a zero exit code on successful analysis, regardless of the grade.

6.3. The tool SHALL NOT crash on malformed HTML. The parser must tolerate broken markup.
