# AI-508 Recommendations Engine Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in RFC 2119.

---

## 7. Recommendations

### 7.1. General Behavior

7.1.1. The tool SHALL generate actionable recommendations for each analysis category that scores below 90.

7.1.2. The tool SHALL NOT generate recommendations for categories scoring 90 or above.

7.1.3. Recommendations SHALL be derived entirely from the existing `AnalysisResult` data. The engine SHALL NOT perform additional HTTP requests or HTML parsing.

7.1.4. Recommendations SHALL reference concrete details from the analyzed page (e.g., element counts, missing tags) rather than offering generic advice.

7.1.5. Recommendations SHALL NOT suggest adding elements or metadata that the page already contains.

### 7.2. Recommendation Model

7.2.1. Each recommendation SHALL have the following fields:

| Field      | Type   | Description                                      |
|------------|--------|--------------------------------------------------|
| `message`  | `str`  | A concise, actionable description of the change  |
| `severity` | `enum` | One of `high`, `medium`, or `low`                |
| `category` | `str`  | The analysis category this recommendation targets |

7.2.2. Severity levels SHALL be assigned according to the following criteria:

| Severity | Criteria                                                              |
|----------|-----------------------------------------------------------------------|
| `high`   | Likely to improve the overall grade by a full letter or more          |
| `medium` | Meaningful improvement to the category score                         |
| `low`    | Incremental polish; unlikely to change the letter grade on its own   |

### 7.3. Ordering and Priority

7.3.1. Recommendations SHOULD be ordered by severity, with `high` recommendations appearing first, followed by `medium`, then `low`.

7.3.2. Within the same severity level, recommendations SHOULD be ordered by the category weight (highest weight first), so that the most impactful changes appear earliest.

### 7.4. Per-Category Recommendation Rules

#### 7.4.1. Semantic HTML

7.4.1.1. When the semantic ratio (§3.1.3) is below 50%, the engine SHALL recommend replacing generic containers (`<div>`, `<span>`) with semantic equivalents and SHALL report the current count of generic containers.

7.4.1.2. The engine SHALL identify which semantic elements from the set defined in §3.1.1 are completely absent from the document and SHALL recommend their addition where contextually appropriate.

7.4.1.3. The engine SHOULD suggest specific substitutions based on likely usage patterns:

| Absent Element      | Suggested Context                                         |
|----------------------|-----------------------------------------------------------|
| `<article>`          | Wrap distinct content items (blog posts, cards, listings) |
| `<section>`          | Divide page into thematic groups                          |
| `<aside>`            | Mark supplementary content (sidebars, promos)             |
| `<nav>`              | Wrap navigation link groups                               |
| `<ul>` or `<ol>`     | Convert sequences of sibling elements into lists          |
| `<time>`             | Mark up dates and times with `datetime` attribute         |
| `<address>`          | Wrap contact information                                  |
| `<details>`/`<summary>` | Replace JS-toggled collapsible panels                 |

#### 7.4.2. Content Availability

7.4.2.1. When the page has no meaningful content (§3.2.2), the engine SHALL recommend server-side rendering or static HTML generation as a `high` severity item.

7.4.2.2. When the page has meaningful content but the word count is below 100, the engine SHOULD recommend increasing the amount of content rendered in the initial HTML response.

7.4.2.3. When no `<noscript>` fallback is present (§3.2.4), the engine SHOULD recommend adding `<noscript>` content as a fallback for non-JS clients.

#### 7.4.3. Link Discoverability

7.4.3.1. When non-navigable links are present (§3.3.2), the engine SHALL recommend converting them to real URLs and SHALL report the count of non-navigable links.

7.4.3.2. When the total link count is zero, the engine SHALL recommend adding navigable `<a href>` links to enable crawling and discovery.

7.4.3.3. The engine SHOULD recommend replacing `javascript:` and `href="#"` links with proper anchor tags that use real URLs.

#### 7.4.4. Structured Data

7.4.4.1. When JSON-LD is absent (§3.4.1), the engine SHALL recommend adding a JSON-LD block with at minimum a `@type` and `name` property.

7.4.4.2. When Open Graph tags are absent (§3.4.2), the engine SHALL recommend adding `og:title`, `og:description`, `og:image`, and `og:url` meta tags.

7.4.4.3. When the meta description is absent (§3.4.3), the engine SHALL recommend adding a `<meta name="description">` tag.

#### 7.4.5. Metadata & Discoverability

7.4.5.1. When the `<title>` element is missing or empty (§3.5.1), the engine SHALL recommend adding a descriptive `<title>`.

7.4.5.2. When the canonical URL is missing (§3.5.2), the engine SHALL recommend adding a `<link rel="canonical">` tag.

7.4.5.3. When the sitemap reference is missing (§3.5.3), the engine SHALL recommend adding a `<link rel="sitemap">` tag pointing to the site's XML sitemap.

7.4.5.4. When the robots meta tag is missing (§3.5.4), the engine SHOULD recommend adding a `<meta name="robots">` tag with appropriate directives.

### 7.5. Architecture

7.5.1. Each analysis category SHALL have a dedicated recommender function that accepts the corresponding analysis result dataclass and returns a list of `Recommendation` objects.

7.5.2. Adding recommendations for a new category SHALL require only adding a new recommender function. The engine's core logic SHALL NOT require modification.

7.5.3. Recommender functions SHALL be pure functions with no side effects. They SHALL be testable in isolation with no dependencies beyond the input dataclass.

---

## 8. Recommendations Output

8.1. Recommendations SHALL be appended to the `Report` model alongside the existing category scores and findings.

8.2. Recommendations SHALL appear in the plain-text report output below each category's findings, visually distinct from findings.

8.3. Each recommendation line SHALL display its severity and message.

8.4. The tool MAY accept a `--no-recommendations` flag to suppress recommendation output.

8.5. The tool SHALL NOT alter the existing score or grade output format. Recommendations are additive only.
