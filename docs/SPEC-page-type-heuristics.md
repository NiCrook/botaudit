# BotAudit Per-Page Type Heuristics Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

BotAudit applies the same scoring expectations to every page regardless of its purpose. A product page, a blog post, a documentation page, and a homepage are all measured against identical criteria and receive identical recommendations.

In practice, different page types have different AI-accessibility priorities:

- A **product page** without `Product` schema is a significant missed opportunity — structured data is essential for AI shopping assistants and rich search results.
- A **blog article** without `Article` schema, `datePublished`, and author information is harder for AI systems to contextualize and cite.
- A **documentation page** without strong navigation and high word count is failing at its core mission — content availability and link discoverability matter most.
- A **homepage** is expected to provide strong metadata and site-level signals rather than deep article content.

This specification introduces page-type detection heuristics that classify each analyzed page into a type, then generate **type-aware recommendations** — more specific, more actionable advice tailored to what the page *should* have given its purpose. Detection is advisory: it does not alter category scores or weights, which remain under user control via `--weight` and `--weight-profile`.

---

## Functional Requirements

### FR-1. Supported Page Types

FR-1.1. The tool SHALL classify each analyzed page into exactly one of the following types:

| Type | Description |
|------|-------------|
| `article` | Blog posts, news articles, opinion pieces, long-form written content |
| `product` | E-commerce product detail pages |
| `documentation` | Technical documentation, API references, guides, tutorials |
| `listing` | Category pages, search results, index/archive pages, sitemaps |
| `homepage` | Site root or primary landing page |
| `generic` | Fallback when no type-specific signals are detected |

FR-1.2. The type list SHALL be defined as a module-level constant (e.g., an enum or string set), making it straightforward to extend with new types.

### FR-2. Detection Heuristics

FR-2.1. The tool SHALL determine page type by evaluating **signals** from data already collected during analysis. The tool SHALL NOT make additional HTTP requests for page-type detection.

FR-2.2. Each signal SHALL contribute a weighted vote toward one or more page types. The type with the highest cumulative vote SHALL be selected. When no type exceeds a minimum confidence threshold, the tool SHALL classify the page as `generic`.

FR-2.3. The minimum confidence threshold SHALL be a module-level constant. The initial value SHOULD be `2.0`.

FR-2.4. The tool SHALL evaluate the following signal categories:

#### FR-2.4.1. JSON-LD `@type` Signals

The tool SHALL use recognized JSON-LD `@type` values (already extracted by structured data analysis) as strong indicators:

| `@type` Value(s) | Detected Type | Vote Weight |
|-------------------|---------------|-------------|
| `Article`, `NewsArticle`, `BlogPosting`, `Review` | `article` | 3.0 |
| `Product`, `Offer`, `AggregateRating` | `product` | 3.0 |
| `HowTo`, `Course`, `SoftwareApplication` | `documentation` | 2.0 |
| `ItemList`, `CollectionPage`, `BreadcrumbList` | `listing` | 2.0 |
| `WebSite`, `Organization` | `homepage` | 1.5 |
| `FAQPage` | `documentation` | 2.0 |
| `Event`, `Recipe`, `JobPosting` | `article` | 1.5 |

FR-2.4.2. When multiple JSON-LD blocks are present with different `@type` values, each SHALL contribute its vote independently.

FR-2.4.3. `BreadcrumbList` SHALL only vote for `listing` when it is the **sole** typed block. When present alongside other types (e.g., `Article` + `BreadcrumbList`), the `BreadcrumbList` vote SHALL be suppressed, as breadcrumbs are a common co-occurrence rather than a page-type signal.

#### FR-2.4.4. Open Graph `og:type` Signals

The tool SHALL use the `og:type` meta tag value as a supporting indicator:

| `og:type` Value | Detected Type | Vote Weight |
|-----------------|---------------|-------------|
| `article` | `article` | 2.0 |
| `product`, `product.item` | `product` | 2.0 |
| `website` | `homepage` | 1.0 |
| `profile` | `generic` | 0 (no vote) |

FR-2.4.5. The `og:type` value SHALL be matched case-insensitively. Unrecognized values SHALL contribute no vote.

#### FR-2.4.6. URL Path Pattern Signals

The tool SHALL match the URL path against common patterns:

| Pattern (case-insensitive) | Detected Type | Vote Weight |
|---------------------------|---------------|-------------|
| Path is exactly `/` or `/index.html` | `homepage` | 2.0 |
| Path contains `/blog/`, `/post/`, `/news/`, `/article/` | `article` | 1.5 |
| Path contains `/product/`, `/item/`, `/shop/`, `/store/` | `product` | 1.5 |
| Path contains `/docs/`, `/documentation/`, `/guide/`, `/tutorial/`, `/reference/`, `/api/` | `documentation` | 1.5 |
| Path contains `/category/`, `/tag/`, `/archive/`, `/search`, `/page/` | `listing` | 1.5 |

FR-2.4.7. URL pattern matching SHALL use substring matching on the normalized (lowercased) path component of the URL. Only the first matching pattern SHALL contribute a vote; patterns SHALL be evaluated in the order listed above to prefer more specific matches.

#### FR-2.4.8. HTML Structure Signals

The tool SHALL use HTML element presence (already counted during semantic HTML analysis) as supporting indicators:

| Signal | Detected Type | Vote Weight |
|--------|---------------|-------------|
| `<article>` element present | `article` | 1.5 |
| `<time>` element present | `article` | 0.5 |
| Word count > 500 AND `<article>` present | `article` | 1.0 |
| `<code>` or `<pre>` elements present (count ≥ 3) | `documentation` | 1.5 |
| Multiple `<h2>` or `<h3>` elements (count ≥ 5) AND `<code>` present | `documentation` | 1.0 |
| Multiple `<li>` items with links (count ≥ 10 navigable links) | `listing` | 1.0 |

FR-2.4.9. HTML structure signals SHALL be derived from data already available in `AnalysisResult` or from counts computable from the parsed HTML without additional fetches.

#### FR-2.4.10. Meta Tag Signals

The tool SHALL check for page-type indicators in meta tags:

| Signal | Detected Type | Vote Weight |
|--------|---------------|-------------|
| `<meta name="pagetype" content="...">` or `<meta property="pagetype" content="...">` with recognized value | Per value | 2.0 |

FR-2.4.11. Recognized `pagetype` meta values SHALL map to detected types using the same mappings as `og:type` (FR-2.4.4), plus: `docs` → `documentation`, `category` → `listing`, `home` → `homepage`.

### FR-3. Detection Confidence

FR-3.1. The tool SHALL compute a confidence score for the detected page type, defined as the ratio of the winning type's cumulative vote to the total votes cast across all types.

FR-3.2. The confidence SHALL be expressed as one of three levels:

| Level | Condition |
|-------|-----------|
| `high` | Winning vote ≥ 4.0 AND confidence ratio ≥ 0.6 |
| `medium` | Winning vote ≥ 2.0 AND confidence ratio ≥ 0.4 |
| `low` | All other cases above the minimum threshold |

FR-3.3. When the page is classified as `generic` (no type met the minimum threshold), the confidence level SHALL be reported as `none`.

### FR-4. Type-Aware Recommendations

FR-4.1. When a non-generic page type is detected, the recommendation engine SHALL generate **additional** type-specific recommendations alongside the existing category recommendations. Type-aware recommendations SHALL NOT replace existing recommendations.

FR-4.2. Type-aware recommendations SHALL be appended to the relevant category's recommendation list, grouped with the category they relate to.

FR-4.3. The tool SHALL generate type-aware recommendations from the following table. Each recommendation SHALL only be generated when its trigger condition is met:

#### Article Pages

| Trigger | Recommendation | Severity | Category |
|---------|---------------|----------|----------|
| No `Article`/`NewsArticle`/`BlogPosting` JSON-LD `@type` | Add Article schema with `headline`, `author`, and `datePublished` for AI citation and search features | `high` | Structured Data |
| JSON-LD present with article type but missing `datePublished` | Add `datePublished` to Article schema — AI systems use publication date for recency and relevance ranking | `medium` | Structured Data |
| JSON-LD present with article type but missing `author` | Add `author` to Article schema — AI assistants use authorship for source attribution | `medium` | Structured Data |
| No `<article>` element wrapping main content | Wrap the main content in an `<article>` element to help AI parsers identify the primary content | `medium` | Semantic HTML |
| Missing `og:type` or `og:type` is not `article` | Set `og:type` to `article` for consistent page-type signaling across AI and social platforms | `low` | Structured Data |

#### Product Pages

| Trigger | Recommendation | Severity | Category |
|---------|---------------|----------|----------|
| No `Product` JSON-LD `@type` | Add Product schema with `name`, `description`, and pricing for AI shopping assistants and rich search results | `high` | Structured Data |
| `Product` schema present but missing `description` | Add `description` to Product schema — AI comparison tools rely on structured product descriptions | `medium` | Structured Data |
| `Product` schema present but no `Offer` with `price` | Add an `Offer` with `price` and `priceCurrency` to Product schema for AI price comparison | `medium` | Structured Data |
| Meta description absent or too short | Add a descriptive meta description summarizing the product — AI assistants use this as a product summary | `medium` | Structured Data |

#### Documentation Pages

| Trigger | Recommendation | Severity | Category |
|---------|---------------|----------|----------|
| Word count < 200 | Documentation pages should render substantive content server-side — AI systems cannot execute JavaScript to reveal hidden content | `high` | Content Availability |
| Navigable link ratio < 0.8 | Documentation pages depend on strong navigation — ensure all links use real URLs, not JavaScript handlers | `medium` | Link Discoverability |
| No `<nav>` element | Add a `<nav>` element for documentation navigation — AI crawlers use it to discover related pages | `medium` | Semantic HTML |
| No `HowTo` or `Course` schema AND content contains step-like structures | Consider adding HowTo schema for tutorial/guide content to enable AI step-by-step presentation | `low` | Structured Data |

#### Homepage Pages

| Trigger | Recommendation | Severity | Category |
|---------|---------------|----------|----------|
| No `WebSite` or `Organization` JSON-LD `@type` | Add WebSite or Organization schema to the homepage — AI systems use this to understand site identity and purpose | `medium` | Structured Data |
| Missing canonical URL | Homepages should have a canonical URL to prevent AI systems from indexing duplicate versions | `medium` | Metadata & Discoverability |
| No sitemap reference | Add a `<link rel="sitemap">` to the homepage — AI crawlers use it as the primary entry point for site discovery | `medium` | Metadata & Discoverability |

#### Listing Pages

| Trigger | Recommendation | Severity | Category |
|---------|---------------|----------|----------|
| No `ItemList` or `CollectionPage` JSON-LD | Add ItemList schema to listing pages — AI systems use it to understand page structure and item relationships | `medium` | Structured Data |
| Low navigable link ratio (< 0.7) | Listing pages are navigation-heavy — ensure category and item links use real URLs for AI discoverability | `medium` | Link Discoverability |

FR-4.4. Type-aware recommendations SHALL only be generated when the parent category scores below the recommendation threshold (< 90), consistent with existing recommendation behavior (`SPEC-recommendations.md`).

FR-4.5. Type-aware recommendations SHALL include a prefix indicating they are type-specific: the recommendation message SHALL begin with `[{type}]` (e.g., `[article] Add Article schema...`).

FR-4.6. The type-aware recommendation table SHALL be defined as a constant data structure, making it straightforward to add new types or adjust triggers without modifying control flow.

### FR-5. Detection Override

FR-5.1. The tool SHALL accept a `--page-type` flag that forces the detected page type to a specific value, bypassing heuristic detection.

FR-5.2. The `--page-type` value SHALL be one of the supported type names (FR-1.1) or `auto` (the default, meaning heuristic detection). Matching SHALL be case-insensitive.

FR-5.3. If the `--page-type` value does not match a supported type or `auto`, the tool SHALL print an error to stderr listing the valid values and exit with code 2.

FR-5.4. When `--page-type` is explicitly set (not `auto`), the confidence level SHALL be reported as `override`.

FR-5.5. In batch mode and crawl mode, the `--page-type` flag SHALL apply uniformly to all URLs. The tool SHALL NOT support per-URL type overrides in the MVP.

### FR-6. Disabling Page-Type Detection

FR-6.1. The tool SHALL accept a `--no-page-type` flag that disables page-type detection entirely.

FR-6.2. When `--no-page-type` is active, the tool SHALL skip all detection heuristics, report no page type, and generate no type-aware recommendations.

FR-6.3. `--no-page-type` and `--page-type` SHALL be mutually exclusive. If both are specified, the tool SHALL print an error to stderr and exit with code 2.

---

## Output

### FR-7. Output Format Integration

FR-7.1. The detected page type SHALL be displayed in all output formats.

FR-7.2. In text output, the page type SHALL appear in the report header, after the URL and before category results:

```
URL: https://example.com/blog/my-post
Page type: article (high confidence)
Overall grade: B (82/100)
```

When detection is disabled or the type is `generic`:

```
URL: https://example.com/unknown
Page type: generic
Overall grade: C (71/100)
```

FR-7.3. In JSON output, a `page_type` object SHALL be added to each URL result:

```json
{
  "url": "https://example.com/blog/my-post",
  "page_type": {
    "type": "article",
    "confidence": "high",
    "signals": [
      {"source": "json_ld", "type_vote": "article", "weight": 3.0, "detail": "@type: Article"},
      {"source": "og_type", "type_vote": "article", "weight": 2.0, "detail": "og:type=article"},
      {"source": "url_path", "type_vote": "article", "weight": 1.5, "detail": "/blog/"}
    ]
  }
}
```

FR-7.4. The `signals` array SHALL list every signal that contributed a non-zero vote, providing transparency into the detection reasoning.

FR-7.5. When page-type detection is disabled (`--no-page-type`), the `page_type` key SHALL be absent from JSON output.

FR-7.6. When the type is `generic`, the `signals` array SHALL be empty and `confidence` SHALL be `"none"`.

FR-7.7. In CSV output, a `page_type` column SHALL be added after the `url` column, containing the type string (e.g., `article`). No confidence or signal detail is included in CSV.

FR-7.8. In HTML output, the page type SHALL appear as a badge or label near the URL in the report header. The confidence level MAY be indicated visually (e.g., color or icon).

### FR-8. Findings

FR-8.1. The detected page type SHALL be reported as a finding in a dedicated "Page Type" section that appears before category results:

FR-8.1.1. When a non-generic type is detected: `Detected page type: {type} ({confidence} confidence).`

FR-8.1.2. When the type is `generic`: `No specific page type detected.`

FR-8.1.3. When the type is overridden via `--page-type`: `Page type set to: {type} (manual override).`

FR-8.2. When confidence is `high` or `medium`, the findings SHOULD include a brief summary of the strongest signal: `Primary signal: {description}` (e.g., `Primary signal: JSON-LD @type Article`).

---

## Exit Codes

### FR-9. Exit Code Behavior

FR-9.1. Page-type detection SHALL NOT alter exit code behavior. All exit code semantics defined in the base spec, `SPEC-batch.md`, and `SPEC-crawl.md` SHALL apply unchanged.

FR-9.2. Invalid `--page-type` values SHALL exit with code 2, consistent with other argument validation failures.

---

## Non-Functional Requirements

### NFR-1. Performance

NFR-1.1. Page-type detection SHALL be performed entirely from data already collected during analysis (HTML content, JSON-LD types, OG tags, URL, link counts). The tool SHALL NOT make additional HTTP requests.

NFR-1.2. The detection algorithm SHALL be O(n) in the number of signals evaluated, which is bounded by a small constant. Detection SHOULD add negligible latency.

NFR-1.3. In batch and crawl modes, detection SHALL be performed independently per URL. No cross-page inference SHALL be attempted.

### NFR-2. Graceful Degradation

NFR-2.1. When no signals are present (e.g., a minimal or empty HTML page), the tool SHALL classify the page as `generic` without error.

NFR-2.2. Conflicting signals (e.g., `Product` schema on a page with `/blog/` in the URL) SHALL be resolved by vote weight — the strongest signal wins. The tool SHALL NOT warn about conflicts.

NFR-2.3. Unrecognized JSON-LD `@type` values, OG types, or URL patterns SHALL be silently ignored. They SHALL NOT affect detection or cause errors.

### NFR-3. Backward Compatibility

NFR-3.1. When `--page-type` and `--no-page-type` are both absent (the default), page-type detection SHALL be enabled automatically. Existing behavior is augmented, not altered — no existing scores, findings, or recommendations change. Only additional type-aware recommendations are introduced.

NFR-3.2. The `Report` dataclass SHALL be extended with an optional `page_type` field. The field SHALL default to `None`, preserving backward compatibility for code that constructs `Report` objects without page-type data.

NFR-3.3. No existing function signatures SHALL change. New parameters SHALL use keyword arguments with defaults that preserve current behavior.

NFR-3.4. Type-aware recommendations are additive. A page that previously received no recommendations (score ≥ 90 in all categories) SHALL continue to receive no recommendations, regardless of detected type.

### NFR-4. Maintainability

NFR-4.1. Page-type detection logic SHALL be implemented in a new module `page_type.py` within the `src/botaudit/` package. This keeps detection isolated from analysis and grading.

NFR-4.2. The signal-to-type vote mappings (FR-2.4) SHALL be defined as module-level constant dictionaries, making it straightforward to add new signals or adjust vote weights.

NFR-4.3. The type-aware recommendation table (FR-4.3) SHALL be defined as a constant data structure in `recommendations.py`, co-located with existing recommendation logic.

NFR-4.4. Adding a new page type SHALL require: (1) adding the type to the type constant, (2) adding signal mappings for the type, and (3) adding type-aware recommendations. No other code changes SHALL be necessary.

### NFR-5. Testability

NFR-5.1. The detection function SHALL be testable as a pure function — given an `AnalysisResult` and a URL string, it returns a page-type result. No HTTP requests, no side effects.

NFR-5.2. Tests SHALL verify that:

**Detection:**
- A page with `Article` JSON-LD is detected as `article`.
- A page with `Product` JSON-LD is detected as `product`.
- A page with `/docs/` in the URL and `<code>` elements is detected as `documentation`.
- A page at URL path `/` is detected as `homepage`.
- A page with `ItemList` JSON-LD is detected as `listing`.
- A page with no signals is detected as `generic`.
- Multiple signals for the same type increase the vote total.
- Conflicting signals resolve to the highest-voted type.
- `BreadcrumbList` alone votes `listing`; alongside `Article` it is suppressed.
- `og:type=article` contributes a vote for `article`.
- URL pattern matching is case-insensitive.
- Only the first matching URL pattern contributes a vote.

**Confidence:**
- A page with a single weak signal has `low` confidence.
- A page with multiple strong signals has `high` confidence.
- A `generic` page has `none` confidence.
- A manually overridden page has `override` confidence.

**Recommendations:**
- An `article` page without `Article` schema receives the high-severity structured data recommendation.
- A `product` page without `Product` schema receives the high-severity recommendation.
- A `documentation` page with low word count receives the content availability recommendation.
- Type-aware recommendations are not generated when the category scores ≥ 90.
- Type-aware recommendations are prefixed with `[{type}]`.
- A `generic` page receives no type-aware recommendations.

**CLI:**
- `--page-type article` forces detection to `article` with `override` confidence.
- `--page-type auto` enables heuristic detection (default behavior).
- `--page-type invalid` exits with code 2.
- `--no-page-type` disables detection entirely.
- `--no-page-type` combined with `--page-type` exits with code 2.

**Output:**
- Text output includes the page type line in the header.
- JSON output includes the `page_type` object with signals.
- CSV output includes the `page_type` column.
- `--no-page-type` omits `page_type` from JSON output.

NFR-5.3. Integration tests SHALL verify that page-type detection propagates through the full pipeline (fetch → analyze → detect type → score → recommend → report) and that type-aware recommendations appear in output.

---

## Data Model

### FR-10. Result Dataclasses

FR-10.1. The following dataclasses SHALL be defined in `page_type.py`:

```python
@dataclass
class PageTypeSignal:
    """A single signal contributing to page-type detection."""
    source: str          # "json_ld", "og_type", "url_path", "html_structure", "meta_tag"
    type_vote: str       # The page type this signal votes for
    weight: float        # Vote weight
    detail: str          # Human-readable detail (e.g., "@type: Article")

@dataclass
class PageTypeResult:
    """Result of page-type detection for a single URL."""
    page_type: str              # One of the supported types or "generic"
    confidence: str             # "high", "medium", "low", "none", or "override"
    signals: list[PageTypeSignal] = field(default_factory=list)
```

FR-10.2. The `Report` dataclass in `models.py` SHALL be extended with:

```python
@dataclass
class Report:
    url: str
    categories: list[CategoryResult]
    overall_score: float
    grade: str
    page_type: PageTypeResult | None = None  # NEW — None when detection disabled
```

FR-10.3. The `page_type` field SHALL default to `None` to maintain backward compatibility.

---

## CLI Interface Summary

```
botaudit https://example.com                          # Auto-detects page type
botaudit https://example.com --page-type product      # Forces page type to product
botaudit https://example.com --no-page-type           # Disables page-type detection
botaudit https://example.com --format json             # JSON output includes page_type object
```

| Flag | Short | Type | Default | Description |
|------|-------|------|---------|-------------|
| `--page-type` | | string | `auto` | Force page type detection to a specific type. Valid values: `auto`, `article`, `product`, `documentation`, `listing`, `homepage`, `generic` |
| `--no-page-type` | | flag | — | Disable page-type detection entirely |
