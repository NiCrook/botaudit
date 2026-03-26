# BotAudit Deeper Structured Data Validation Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

The Structured Data category (`SPEC.md` §3.4) currently performs **presence-only** checks: it awards points when JSON-LD, Open Graph tags, or a meta description exist in the HTML, regardless of whether their content is valid, complete, or useful to an AI consumer.

Current scoring breakdown (100 points):

| Signal | Points | Condition |
|--------|--------|-----------|
| JSON-LD present | 40 | At least one `<script type="application/ld+json">` block exists |
| Open Graph present | 30 | At least one `<meta property="og:*">` tag exists |
| Meta description present | 30 | `<meta name="description">` with non-empty `content` |

This means a page with a single empty JSON-LD block `{}`, one `og:locale` tag, and a one-word meta description scores a perfect 100 — the same as a page with rich, validated schema.org markup, complete OG metadata, and a well-crafted description.

This specification deepens the Structured Data category to validate **quality and completeness** of structured data, not merely its existence. Presence remains rewarded, but partial credit is introduced for structural validity, property completeness, and adherence to schema.org conventions.

---

## Functional Requirements

### FR-1. JSON-LD Validation

#### FR-1.1. Parsing

FR-1.1.1. The tool SHALL attempt to parse every `<script type="application/ld+json">` block as JSON using Python's `json` module.

FR-1.1.2. When parsing fails (malformed JSON), the block SHALL be counted as present but invalid. The tool SHALL NOT raise an exception or produce a stack trace.

FR-1.1.3. When a block parses successfully, the tool SHALL inspect its top-level structure. A valid JSON-LD object SHALL be a JSON object (not an array or scalar) containing an `@type` field, OR an array of such objects, OR an object with a `@graph` key whose value is an array of typed objects.

FR-1.1.4. The tool SHALL count the number of parseable blocks and the number of blocks that contain at least one typed object (per FR-1.1.3).

#### FR-1.2. `@context` Validation

FR-1.2.1. The tool SHALL check for the presence of an `@context` field in each JSON-LD object.

FR-1.2.2. The `@context` field SHALL be considered valid when its value is the string `"https://schema.org"`, `"http://schema.org"`, or an object/array that includes one of these URLs.

FR-1.2.3. A missing or unrecognized `@context` SHALL NOT prevent further analysis of the block. The tool SHALL note the absence in findings but continue validation.

#### FR-1.3. `@type` Validation

FR-1.3.1. The tool SHALL extract the `@type` value from each JSON-LD object.

FR-1.3.2. The tool SHALL maintain a constant list of **recognized schema.org types** commonly used on the web:

```
Article, NewsArticle, BlogPosting, WebPage, WebSite, Organization, LocalBusiness,
Person, Product, Offer, BreadcrumbList, FAQPage, HowTo, Event, Recipe, VideoObject,
ImageObject, ItemList, CollectionPage, SearchAction, SiteNavigationElement,
SoftwareApplication, Course, Review, AggregateRating, MedicalEntity, JobPosting,
CreativeWork
```

FR-1.3.3. The tool SHALL classify each `@type` as **recognized** (present in the list) or **unrecognized**. Unrecognized types SHALL still be reported and SHALL NOT reduce the score — the list is advisory, not exhaustive.

FR-1.3.4. The tool SHALL report the list of `@type` values found across all blocks.

#### FR-1.4. Required Property Validation

FR-1.4.1. For each recognized `@type`, the tool SHALL check for the presence of a set of **minimum recommended properties**. These properties represent the subset that schema.org and Google's structured data guidelines consider essential for the type to be useful:

| @type | Minimum Recommended Properties |
|-------|-------------------------------|
| `Article`, `NewsArticle`, `BlogPosting` | `headline`, `author`, `datePublished` |
| `WebSite` | `name`, `url` |
| `WebPage` | `name`, `url` |
| `Organization` | `name`, `url` |
| `LocalBusiness` | `name`, `address` |
| `Person` | `name` |
| `Product` | `name`, `description` |
| `Offer` | `price`, `priceCurrency` |
| `BreadcrumbList` | `itemListElement` |
| `FAQPage` | `mainEntity` |
| `HowTo` | `name`, `step` |
| `Event` | `name`, `startDate` |
| `Recipe` | `name`, `recipeIngredient` |
| `VideoObject` | `name`, `uploadDate` |
| `JobPosting` | `title`, `datePosted` |
| `SoftwareApplication` | `name`, `operatingSystem` |
| `Course` | `name`, `provider` |
| `Review` | `itemReviewed`, `author` |

FR-1.4.2. A property SHALL be considered present when it exists as a key in the JSON-LD object and its value is not `null`, an empty string `""`, or an empty array `[]`.

FR-1.4.3. Types not listed in the table above SHALL be exempt from property validation. Presence of a typed JSON-LD object with `@context` is sufficient for those types.

FR-1.4.4. The tool SHALL report, for each typed block, which minimum recommended properties are present and which are missing.

FR-1.4.5. The minimum recommended properties table SHALL be defined as a constant dictionary, making it straightforward to update as schema.org evolves.

### FR-2. Open Graph Validation

#### FR-2.1. Required Properties

FR-2.1.1. The tool SHALL check for the presence of the four **required** Open Graph properties as defined by the Open Graph Protocol:

| Property | Description |
|----------|-------------|
| `og:title` | Title of the page |
| `og:type` | Type of content (e.g., `website`, `article`) |
| `og:image` | URL to an image representing the content |
| `og:url` | Canonical URL of the page |

FR-2.1.2. Each required property SHALL be considered present when a `<meta property="og:*">` tag exists with a non-empty `content` attribute.

FR-2.1.3. The tool SHALL report which required properties are present and which are missing.

#### FR-2.2. Recommended Properties

FR-2.2.1. The tool SHALL additionally check for the presence of these **recommended** Open Graph properties:

| Property | Description |
|----------|-------------|
| `og:description` | Brief description of the content |
| `og:site_name` | Name of the overall site |

FR-2.2.2. Missing recommended properties SHALL be reported in findings but SHALL carry less scoring weight than missing required properties (see FR-4).

#### FR-2.3. Property Content Validation

FR-2.3.1. The tool SHALL NOT fetch or validate URLs found in `og:image` or `og:url` values. Presence of a non-empty string is sufficient.

FR-2.3.2. The tool SHALL NOT validate the `og:type` value against the Open Graph type registry. Presence of any non-empty value is sufficient.

### FR-3. Meta Description Validation

FR-3.1. The tool SHALL continue to detect the `<meta name="description">` tag as defined in `SPEC.md` §3.4.3.

FR-3.2. When a meta description is present, the tool SHALL measure its length in characters (after trimming whitespace).

FR-3.3. The tool SHALL classify the meta description length as:

| Classification | Length | Rationale |
|----------------|--------|-----------|
| Too short | < 50 characters | Insufficient for meaningful search/AI snippets |
| Optimal | 50–160 characters | Standard recommended range for search engines |
| Too long | > 160 characters | Likely to be truncated in search results and AI summaries |

FR-3.4. The length classification SHALL be reported in findings.

FR-3.5. The tool SHALL NOT evaluate the semantic quality or relevance of the description content. Length-based classification is sufficient.

### FR-4. Revised Scoring

FR-4.1. The Structured Data category SHALL retain a total possible score of 100 points.

FR-4.2. The scoring breakdown SHALL be revised as follows:

| Signal | Points | Condition |
|--------|--------|-----------|
| **JSON-LD** | | |
| JSON-LD present | 10 | At least one `<script type="application/ld+json">` block exists |
| JSON-LD parseable | 5 | At least one block parses as valid JSON |
| `@context` present | 5 | At least one block has a valid schema.org `@context` |
| `@type` present | 5 | At least one block contains an `@type` field |
| Minimum properties satisfied | 10 | At least one typed block has all minimum recommended properties for its `@type` (per FR-1.4.1). Types not in the table automatically satisfy this signal. |
| **Subtotal JSON-LD** | **35** | |
| **Open Graph** | | |
| Open Graph present | 10 | At least one `og:*` meta tag exists |
| Required OG properties complete | 10 | All four required OG properties (FR-2.1.1) present with non-empty content |
| Recommended OG properties present | 5 | Both `og:description` and `og:site_name` present |
| **Subtotal Open Graph** | **25** | |
| **Meta Description** | | |
| Meta description present | 10 | `<meta name="description">` with non-empty content |
| Meta description optimal length | 5 | Length is 50–160 characters (FR-3.3) |
| **Subtotal Meta Description** | **15** | |
| **Twitter Cards** | | |
| Twitter card present | 5 | At least one `<meta name="twitter:*">` or `<meta property="twitter:*">` tag exists with non-empty content |
| **Subtotal Twitter Cards** | **5** | |
| **Microdata** | | |
| Microdata present | 5 | At least one element with an `itemscope` attribute exists |
| **Subtotal Microdata** | **5** | |
| **Multiple Formats Bonus** | | |
| Multiple structured data formats | 15 | Two or more of JSON-LD, Open Graph, microdata, or Twitter Cards are present |
| **Total** | **100** | |

FR-4.3. The "minimum properties satisfied" signal (10 points) SHALL be awarded when **at least one** typed JSON-LD block passes its property check. Not all blocks need to pass.

FR-4.4. The "multiple structured data formats" signal (15 points) SHALL be awarded when two or more of the following are detected: JSON-LD (at least one parseable block), Open Graph (at least one tag), microdata (at least one `itemscope`), Twitter Cards (at least one tag). Meta description alone SHALL NOT count toward this signal.

FR-4.5. A page with only a meta description and no other structured data SHALL score a maximum of 15 points (meta description present + optimal length).

### FR-5. Twitter Card Detection

FR-5.1. The tool SHALL check for the presence of Twitter Card meta tags: `<meta name="twitter:*">` and `<meta property="twitter:*">` with non-empty `content` attributes.

FR-5.2. The tool SHALL report the list of Twitter Card properties found.

FR-5.3. The tool SHALL NOT validate Twitter Card property completeness beyond presence. Detection of any Twitter Card tag is sufficient for the signal.

### FR-6. Microdata Detection

FR-6.1. The tool SHALL check for the presence of HTML Microdata by searching for elements with an `itemscope` attribute.

FR-6.2. When microdata is found, the tool SHALL report the count of `itemscope` elements and the `itemtype` values found (if present).

FR-6.3. The tool SHALL NOT perform deep validation of microdata property completeness. Presence of `itemscope` is sufficient for the signal.

### FR-7. Findings

#### FR-7.1. JSON-LD Findings

FR-7.1.1. When JSON-LD is present and valid, the findings SHALL include: `JSON-LD present ({N} block(s)): {comma-separated @type list}.`

FR-7.1.2. When JSON-LD is present but unparseable, the findings SHALL include: `JSON-LD present ({N} block(s)) but {M} failed to parse.`

FR-7.1.3. When a typed block is missing minimum recommended properties, the findings SHALL include: `{@type} missing recommended properties: {comma-separated list}.`

FR-7.1.4. When all minimum recommended properties are satisfied, the findings SHALL include: `{@type} has all recommended properties.`

FR-7.1.5. When `@context` is missing or not schema.org, the findings SHALL include: `JSON-LD block missing schema.org @context.`

FR-7.1.6. When JSON-LD is absent, the findings SHALL include: `No JSON-LD found.`

#### FR-7.2. Open Graph Findings

FR-7.2.1. When all four required OG properties are present, the findings SHALL include: `Open Graph complete ({N} tags): all required properties present.`

FR-7.2.2. When OG is present but missing required properties, the findings SHALL include: `Open Graph present ({N} tags) — missing required: {comma-separated list}.`

FR-7.2.3. When OG is absent, the findings SHALL include: `No Open Graph tags found.`

#### FR-7.3. Meta Description Findings

FR-7.3.1. When the meta description is present and optimal length, the findings SHALL include: `Meta description present ({N} chars) — optimal length.`

FR-7.3.2. When the meta description is present but too short, the findings SHALL include: `Meta description present ({N} chars) — below recommended minimum of 50 characters.`

FR-7.3.3. When the meta description is present but too long, the findings SHALL include: `Meta description present ({N} chars) — exceeds recommended maximum of 160 characters.`

FR-7.3.4. When the meta description is absent, the findings SHALL include: `No meta description found.`

#### FR-7.4. Twitter Card Findings

FR-7.4.1. When Twitter Card tags are present, the findings SHALL include: `Twitter Card tags present ({N} tags).`

FR-7.4.2. When Twitter Card tags are absent, the findings SHALL include: `No Twitter Card tags found.`

#### FR-7.5. Microdata Findings

FR-7.5.1. When microdata is present, the findings SHALL include: `Microdata present ({N} itemscope element(s)).`

FR-7.5.2. When microdata is absent, the findings SHALL include: `No microdata found.`

### FR-8. Recommendations

FR-8.1. When JSON-LD is absent, the engine SHALL recommend adding a JSON-LD block as a `high` severity item, consistent with existing behavior (`SPEC-recommendations.md` §7.4.4.1).

FR-8.2. When JSON-LD is present but unparseable, the engine SHALL recommend fixing the JSON syntax as a `high` severity item.

FR-8.3. When JSON-LD is parseable but missing `@context`, the engine SHALL recommend adding `"@context": "https://schema.org"` as a `medium` severity item.

FR-8.4. When a typed block is missing minimum recommended properties, the engine SHALL recommend adding the missing properties as a `medium` severity item, listing the specific properties.

FR-8.5. When Open Graph is absent, the engine SHALL recommend adding the four required OG properties as a `medium` severity item, consistent with existing behavior (`SPEC-recommendations.md` §7.4.4.2).

FR-8.6. When Open Graph is present but missing required properties, the engine SHALL recommend adding the missing required properties as a `medium` severity item, listing which ones are absent.

FR-8.7. When the meta description is absent, the engine SHALL recommend adding one as a `medium` severity item, consistent with existing behavior (`SPEC-recommendations.md` §7.4.4.3).

FR-8.8. When the meta description is present but outside the optimal range (FR-3.3), the engine SHALL recommend adjusting the length as a `low` severity item.

FR-8.9. When fewer than two structured data formats are present, the engine MAY recommend adding an additional format as a `low` severity item, noting that multiple formats improve AI discoverability.

FR-8.10. Structured Data recommendations SHALL only be generated when the category score is below the recommendation threshold (consistent with `SPEC-recommendations.md` §7.1.1).

---

## Output

### FR-9. Output Format Integration

FR-9.1. The deepened findings and recommendations SHALL appear within the existing Structured Data category section in all output formats (text, JSON, CSV, HTML).

FR-9.2. In JSON output, the `structured_data` result object SHALL be extended with validation details:

```json
{
  "structured_data": {
    "json_ld": {
      "present": true,
      "block_count": 2,
      "parseable_count": 2,
      "has_context": true,
      "types": ["Article", "BreadcrumbList"],
      "type_details": [
        {
          "type": "Article",
          "recognized": true,
          "properties_present": ["headline", "author", "datePublished", "image"],
          "properties_missing": [],
          "all_recommended_present": true
        },
        {
          "type": "BreadcrumbList",
          "recognized": true,
          "properties_present": ["itemListElement"],
          "properties_missing": [],
          "all_recommended_present": true
        }
      ]
    },
    "open_graph": {
      "present": true,
      "tags": ["og:title", "og:type", "og:image", "og:url", "og:description"],
      "required_present": ["og:title", "og:type", "og:image", "og:url"],
      "required_missing": [],
      "recommended_present": ["og:description"],
      "recommended_missing": ["og:site_name"]
    },
    "meta_description": {
      "present": true,
      "length": 142,
      "length_classification": "optimal"
    },
    "twitter_cards": {
      "present": true,
      "tags": ["twitter:card", "twitter:site"]
    },
    "microdata": {
      "present": false,
      "itemscope_count": 0,
      "itemtypes": []
    },
    "format_count": 3
  }
}
```

FR-9.3. The extended fields SHALL always be present in JSON output, with sensible defaults when data is absent (empty arrays, `false` booleans, `0` counts).

---

## Exit Codes

### FR-10. Exit Code Behavior

FR-10.1. The deepened validation checks SHALL NOT alter exit code behavior. All exit code semantics defined in the base spec, `SPEC-batch.md`, and `SPEC-crawl.md` SHALL apply unchanged.

---

## Non-Functional Requirements

### NFR-1. Performance

NFR-1.1. All validation SHALL be performed on data already present in the fetched HTML response. The tool SHALL NOT make additional HTTP requests for structured data validation (e.g., SHALL NOT fetch URLs in `og:image` or JSON-LD `url` fields).

NFR-1.2. JSON parsing of JSON-LD blocks SHALL use Python's `json` module (stdlib). The tool SHALL NOT introduce new dependencies for validation.

NFR-1.3. The additional parsing and validation work SHOULD add negligible latency. JSON-LD blocks are typically small (< 10 KB), and property lookups are O(1) dictionary operations.

### NFR-2. Graceful Degradation

NFR-2.1. Malformed JSON in any JSON-LD block SHALL be handled gracefully — the block is counted as present but unparseable, with no stack trace or error output.

NFR-2.2. Unexpected structures within otherwise valid JSON (e.g., `@type` as an array, nested `@graph` objects) SHALL be handled best-effort. The tool SHALL NOT crash on unusual but technically valid JSON-LD.

NFR-2.3. When `@type` is an array (e.g., `["Article", "NewsArticle"]`), the tool SHALL use the **first** value for property validation purposes.

### NFR-3. Backward Compatibility

NFR-3.1. The revised scoring (FR-4) changes point allocations for all existing signals. Score impact for common scenarios:

| Scenario | Old Score | New Score | Delta |
|----------|-----------|-----------|-------|
| No structured data at all | 0 | 0 | 0 |
| Only meta description (optimal length) | 30 | 15 | −15 |
| JSON-LD present (empty `{}`), one OG tag, meta desc | 100 | 25 | −75 |
| Valid JSON-LD with types + all OG required + meta desc (optimal) | 100 | 80 | −20 |
| Full marks: above + recommended OG + Twitter + microdata + multi-format bonus | — | 100 | — |

NFR-3.2. The overall grade impact of score changes SHALL be moderated by the category's 13% default weight. A 20-point reduction in Structured Data reduces the overall score by 2.6 points at most. Sites with no structured data are unaffected.

NFR-3.3. The existing `StructuredDataResult` dataclass SHALL be extended with new fields. New fields SHALL use default values that preserve backward compatibility (e.g., `json_ld_types: list[str] = field(default_factory=list)`).

NFR-3.4. No existing public function signatures SHALL change. New parameters SHALL use keyword arguments with defaults that preserve current behavior.

### NFR-4. Maintainability

NFR-4.1. The deepened analysis logic SHALL be implemented within the existing `analysis.py` module, extending the `analyze_structured_data()` function.

NFR-4.2. The minimum recommended properties table (FR-1.4.1) SHALL be defined as a module-level constant dictionary mapping `@type` strings to lists of property names. Adding or updating type requirements SHALL require only modifying this constant.

NFR-4.3. The recognized schema.org types list (FR-1.3.2) SHALL be defined as a module-level constant set. Adding new types SHALL require only adding entries to this set.

NFR-4.4. The scoring logic in `grading.py` SHALL remain a single function (`score_structured_data`), extended to handle the new signals. The function SHALL remain stateless and derive all scores from the `StructuredDataResult` dataclass.

### NFR-5. Testability

NFR-5.1. The extended `analyze_structured_data()` function SHALL remain testable as a pure function — given a BeautifulSoup object, it returns a `StructuredDataResult`. No HTTP requests, no side effects.

NFR-5.2. Tests SHALL verify that:

**JSON-LD:**
- Valid JSON-LD with `@context`, `@type`, and properties is fully detected.
- Malformed JSON is counted as present but unparseable.
- Missing `@context` is flagged but does not prevent further analysis.
- Missing `@type` is detected and reported.
- `@type` as an array uses the first value.
- `@graph` arrays are traversed to find typed objects.
- Minimum recommended properties are checked for each recognized type.
- Missing recommended properties are listed specifically.
- Unrecognized types pass validation without property checks.
- Multiple JSON-LD blocks are each independently validated.

**Open Graph:**
- All four required properties present awards full OG points.
- Missing one or more required properties reduces the score appropriately.
- Recommended properties (`og:description`, `og:site_name`) are detected independently.
- Empty `content` attributes are treated as absent.

**Meta Description:**
- Length is correctly measured after trimming.
- Classification boundaries: 49 chars → too short, 50 chars → optimal, 160 chars → optimal, 161 chars → too long.
- Absent meta description scores 0 for this sub-category.

**Twitter Cards:**
- `<meta name="twitter:card">` is detected.
- `<meta property="twitter:*">` variant is also detected.
- Empty content is treated as absent.

**Microdata:**
- Elements with `itemscope` are counted.
- `itemtype` attribute values are extracted.
- Absence of microdata is reported cleanly.

**Scoring:**
- Each signal awards the correct number of points independently.
- The multi-format bonus is awarded at exactly 2 formats, not 1.
- A page with all signals present scores exactly 100.
- A page with no structured data scores exactly 0.
- Combinations of partial data score correctly.

**Findings:**
- Each finding message matches the format specified in FR-7.

**Recommendations:**
- Unparseable JSON-LD triggers a high-severity recommendation.
- Missing `@context` triggers a medium-severity recommendation.
- Missing minimum properties triggers a medium-severity recommendation listing the properties.
- Missing required OG properties triggers a recommendation listing which ones.
- Sub-optimal meta description length triggers a low-severity recommendation.

NFR-5.3. Integration tests SHALL verify that the deepened validation propagates through the full pipeline (fetch → analyze → score → report) and that JSON output includes the extended fields.

---

## Data Model

### FR-11. Result Dataclass Extensions

FR-11.1. The `StructuredDataResult` dataclass SHALL be extended with the following fields:

```python
@dataclass
class JsonLdBlock:
    """Validation result for a single JSON-LD block."""
    raw_valid: bool                     # Parsed as valid JSON
    context_present: bool               # Has schema.org @context
    type_value: str                     # @type value (first if array), empty if absent
    recognized_type: bool               # @type is in recognized types list
    properties_present: list[str]       # Minimum recommended properties found
    properties_missing: list[str]       # Minimum recommended properties missing

@dataclass
class StructuredDataResult:
    """3.4 — Structured data analysis."""
    # Existing fields (preserved)
    has_json_ld: bool = False
    json_ld_count: int = 0
    has_open_graph: bool = False
    open_graph_tags: list[str] = field(default_factory=list)
    has_meta_description: bool = False
    meta_description: str = ""

    # New JSON-LD validation fields
    json_ld_parseable_count: int = 0
    json_ld_blocks: list[JsonLdBlock] = field(default_factory=list)

    # New Open Graph validation fields
    og_required_present: list[str] = field(default_factory=list)
    og_required_missing: list[str] = field(default_factory=list)
    og_recommended_present: list[str] = field(default_factory=list)
    og_recommended_missing: list[str] = field(default_factory=list)

    # New meta description validation fields
    meta_description_length: int = 0
    meta_description_length_class: str = ""  # "too_short", "optimal", "too_long", or ""

    # New format detection fields
    has_twitter_cards: bool = False
    twitter_card_tags: list[str] = field(default_factory=list)
    has_microdata: bool = False
    microdata_count: int = 0
    microdata_types: list[str] = field(default_factory=list)
```

FR-11.2. The new `JsonLdBlock` dataclass SHALL be defined in `analysis.py` alongside `StructuredDataResult`.

FR-11.3. All new fields on `StructuredDataResult` SHALL have defaults that produce the same behavior as the current implementation when the deepened analysis is not performed (i.e., empty lists, `0` counts, `False` booleans).

---

## CLI Interface Summary

No new CLI flags are introduced. The deepened validation is automatically applied to the existing Structured Data category.

```
botaudit https://example.com                      # Includes deepened structured data validation
botaudit https://example.com --format json         # JSON output includes extended validation fields
```
