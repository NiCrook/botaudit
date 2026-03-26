# AI-508 LLM Discoverability Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in RFC 2119.

---

## Background

The [llms.txt specification](https://llmstxt.org/) defines a Markdown-formatted file served at a website's root path (`/llms.txt`) that provides LLMs with a curated map of a site's most important resources. The companion file `llms-full.txt` provides an expanded version with all resource content inlined. Meanwhile, `robots.txt` controls crawler access and can explicitly allow or block known AI user-agents.

Together, these three files represent a site's AI-specific infrastructure — the signals that tell AI consumers whether they're welcome and where to find what they need.

This feature adds a new "LLM Discoverability" analysis category to AI-508 that evaluates all three files. It supersedes the MVP constraint in §3.5.5 ("SHALL NOT make a separate request") for these specific resources.

---

## Functional Requirements

### FR-1. Fetching

FR-1.1. The tool SHALL attempt to fetch the following files from the origin of the provided URL:

| File | Example | Purpose |
|------|---------|---------|
| `/robots.txt` | `https://example.com/robots.txt` | AI crawler access policy |
| `/llms.txt` | `https://example.com/llms.txt` | LLM resource map |
| `/llms-full.txt` | `https://example.com/llms-full.txt` | Expanded LLM resource content |

FR-1.2. The tool SHALL make these fetches as separate HTTP GET requests, independent of the primary HTML fetch.

FR-1.3. The tool SHALL use the same User-Agent, timeout, and redirect settings as the primary fetch (§2).

FR-1.4. The tool SHALL treat a 404, 403, or any non-2xx response for any of these files as "not present" and continue analysis without error.

FR-1.5. The tool SHALL treat network errors (DNS failure, timeout, connection refused) for any of these fetches as "not present" and SHALL NOT fail the overall analysis.

FR-1.6. The tool SHALL validate that the response Content-Type is text (e.g., `text/plain`, `text/markdown`). If the response is HTML or another non-text format, the tool SHALL treat the file as "not present."

FR-1.7. The tool SHOULD perform the three fetches concurrently with each other (and with the primary HTML fetch where possible) to minimize total latency.

### FR-2. robots.txt Analysis

FR-2.1. The tool SHALL parse `robots.txt` according to the [Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309.html).

FR-2.2. The tool SHALL check for directives targeting the following known AI user-agents:

| User-Agent | Operator |
|------------|----------|
| `GPTBot` | OpenAI |
| `ChatGPT-User` | OpenAI |
| `Google-Extended` | Google |
| `ClaudeBot` | Anthropic |
| `anthropic-ai` | Anthropic |
| `PerplexityBot` | Perplexity |
| `Bytespider` | ByteDance |
| `CCBot` | Common Crawl |
| `cohere-ai` | Cohere |

FR-2.3. For each AI user-agent, the tool SHALL determine whether it is allowed, blocked (`Disallow: /`), or not mentioned.

FR-2.4. The tool SHALL compute a summary classification:

| Classification | Condition |
|----------------|-----------|
| `open` | No robots.txt present, or no AI user-agents are blocked |
| `partial` | Some AI user-agents are blocked, others are allowed or not mentioned |
| `restrictive` | All known AI user-agents are blocked |

FR-2.5. The tool SHALL use Python's `urllib.robotparser` (stdlib) to parse robots.txt. The tool SHALL NOT implement a custom parser.

FR-2.6. The tool SHALL check for a `Sitemap:` directive in robots.txt and record whether one is present.

### FR-3. llms.txt Structural Validation

FR-3.1. The tool SHALL validate the retrieved llms.txt against the core structural requirements of the specification:

| Element | Required | Description |
|---------|----------|-------------|
| H1 heading (`# ...`) | Yes | Project or site name |
| Blockquote (`> ...`) | No | Short summary of the project |
| H2 sections (`## ...`) | No | Resource categories with link lists |
| `## Optional` section | No | Secondary resources that may be skipped |

FR-3.2. The tool SHALL check that the file begins with exactly one H1 heading.

FR-3.3. The tool SHALL check for the presence of a blockquote summary following the H1.

FR-3.4. The tool SHALL count the number of H2 sections and the number of resource links (Markdown links in list items) within them.

FR-3.5. The tool SHALL detect the presence of an `## Optional` section.

FR-3.6. The tool SHALL report whether the file is structurally valid (has at minimum the required H1).

### FR-4. llms.txt Content Quality Assessment

FR-4.1. The tool SHALL assess whether the blockquote summary, if present, is non-empty and substantive (more than 5 words).

FR-4.2. The tool SHALL count the total number of resource links provided across all sections.

FR-4.3. The tool SHALL check that resource links use valid URL syntax (relative or absolute).

FR-4.4. The tool SHALL detect whether resource links point to Markdown files (`.md` extension), which the llms.txt spec recommends for LLM-friendly content.

FR-4.5. The tool MAY validate that the file size is reasonable (not empty, not excessively large) as a quality signal.

### FR-5. llms-full.txt Detection

FR-5.1. The tool SHALL check for the presence of `/llms-full.txt` at the site origin.

FR-5.2. The tool SHALL validate that the file is non-empty text content.

FR-5.3. The tool SHALL NOT perform deep structural analysis of llms-full.txt. Presence of a valid text response is sufficient.

FR-5.4. llms-full.txt SHALL only be scored when llms.txt is also present. A site with llms-full.txt but no llms.txt SHALL NOT receive credit for llms-full.txt.

### FR-6. Scoring

FR-6.1. The tool SHALL assign a score (0–100) to the LLM Discoverability category.

FR-6.2. Scoring SHALL follow this breakdown:

| Signal | Points | Condition |
|--------|--------|-----------|
| AI crawlers not blocked | 30 | robots.txt is absent, or classification is `open` or `partial` |
| robots.txt explicitly permits AI bots | 5 | At least one AI user-agent has an explicit `Allow` rule |
| Sitemap in robots.txt | 5 | `Sitemap:` directive present in robots.txt |
| llms.txt present | 20 | File exists and returns valid text |
| llms.txt valid structure | 5 | Has required H1 heading |
| llms.txt summary present | 5 | Blockquote with substantive content (>5 words) |
| llms.txt resource links | 10 | At least one H2 section with resource links |
| llms.txt markdown resources | 5 | One or more resource links point to `.md` files |
| llms-full.txt present | 10 | File exists and returns valid, non-empty text |
| robots.txt explicitly permits `ai-508` | 5 | The tool's own user-agent is not blocked |

FR-6.3. When robots.txt is classified as `restrictive` (FR-2.4), the AI crawlers signal SHALL score 0 and the `ai-508` signal SHALL score 0 — capping the maximum category score at 65.

FR-6.4. The tool SHALL NOT award llms.txt structural, summary, resource link, or markdown resource points when llms.txt is not present.

FR-6.5. The tool SHALL NOT award llms-full.txt points when llms.txt is not present (FR-5.4).

FR-6.6. A site with no robots.txt and no llms.txt SHALL score 30 (the "not blocked" baseline).

### FR-7. Grading Integration

FR-7.1. LLM Discoverability SHALL be added as the sixth analysis category.

FR-7.2. The category weights SHALL be redistributed as follows:

| Category | Current Weight | New Weight |
|----------|---------------|------------|
| Content Availability | 30% | 27% |
| Semantic HTML | 25% | 23% |
| Link Discoverability | 20% | 18% |
| Structured Data | 15% | 13% |
| Metadata & Discoverability | 10% | 9% |
| LLM Discoverability (new) | — | 10% |

FR-7.3. The tool MAY increase the LLM Discoverability weight in future versions as llms.txt adoption grows.

FR-7.4. The existing grade thresholds (§4.3) SHALL NOT change.

### FR-8. Output

FR-8.1. The LLM Discoverability category SHALL appear in the report alongside existing categories.

FR-8.2. The findings SHALL report the robots.txt classification (`open`, `partial`, `restrictive`, or not present) and list any blocked AI user-agents by name.

FR-8.3. When llms.txt is not present, the findings SHALL state that no llms.txt file was found.

FR-8.4. When llms.txt is present, the findings SHALL report: structural validity, whether a summary exists, the number of resource sections, the number of resource links, and whether llms-full.txt is also available.

FR-8.5. The tool MAY display a truncated preview of the llms.txt H1 and summary in the findings.

### FR-9. Recommendations Integration

FR-9.1. When the LLM Discoverability category scores below 90, the tool SHALL generate recommendations per the recommendation engine spec (§7).

FR-9.2. When robots.txt blocks all AI crawlers (`restrictive`), the engine SHALL recommend reviewing AI crawler access policies as a `high` severity item, noting which user-agents are blocked.

FR-9.3. When robots.txt blocks some AI crawlers (`partial`), the engine SHOULD recommend reviewing the blocking policy as a `medium` severity item.

FR-9.4. When llms.txt is absent, the engine SHALL recommend creating a `/llms.txt` file with at minimum an H1 and summary as a `medium` severity item.

FR-9.5. When llms.txt is present but lacks a blockquote summary, the engine SHALL recommend adding one as a `low` severity item.

FR-9.6. When llms.txt is present but has no resource links, the engine SHALL recommend adding H2 sections with links to key resources as a `medium` severity item.

FR-9.7. When resource links do not point to Markdown files, the engine SHOULD recommend providing `.md` versions of linked pages as a `low` severity item.

FR-9.8. When llms.txt is present but llms-full.txt is not, the engine SHOULD recommend generating an llms-full.txt as a `low` severity item.

FR-9.9. When robots.txt lacks a `Sitemap:` directive, the engine SHOULD recommend adding one as a `low` severity item.

---

## Non-Functional Requirements

### NFR-1. Performance

NFR-1.1. The three supplementary fetches (robots.txt, llms.txt, llms-full.txt) SHALL be performed concurrently with each other to minimize total latency.

NFR-1.2. The supplementary fetches SHOULD be performed concurrently with the primary HTML fetch where the implementation allows.

NFR-1.3. The feature adds at most three additional HTTP requests per invocation.

NFR-1.4. The total added time for sites missing all three files SHOULD be negligible — three concurrent 404 responses.

### NFR-2. Graceful Degradation

NFR-2.1. The tool SHALL produce a complete, valid report even when any or all supplementary fetches fail.

NFR-2.2. The absence of robots.txt, llms.txt, or llms-full.txt SHALL NOT produce warnings or error output. These are expected conditions.

NFR-2.3. The tool SHALL NOT crash or produce a stack trace if any fetched file is malformed, empty, or in an unexpected format.

### NFR-3. Proportional Impact

NFR-3.1. A site with no llms.txt, no llms-full.txt, and no robots.txt but perfect scores in all other categories SHALL still receive a grade of A (minimum overall score: 100 × 0.90 + 30 × 0.10 = 93.0).

NFR-3.2. A site that actively blocks all AI crawlers via robots.txt SHALL have its LLM Discoverability score capped (FR-6.3) but this alone SHALL NOT reduce the overall grade below B for an otherwise well-scoring site.

NFR-3.3. The presence of a well-formed llms.txt SHALL NOT be able to compensate for fundamentally poor AI accessibility (e.g., an empty JS shell).

### NFR-4. Configurability

NFR-4.1. The tool MAY accept a `--skip-llm-discovery` flag to disable all supplementary fetches (robots.txt, llms.txt, llms-full.txt), restoring MVP behavior and avoiding additional HTTP requests.

NFR-4.2. When supplementary fetches are skipped, the LLM Discoverability category SHALL be omitted from the report and its weight SHALL be redistributed proportionally across the remaining categories.

### NFR-5. Maintainability

NFR-5.1. The LLM Discoverability analysis SHALL be implemented as a self-contained module, consistent with the existing architecture (one analyzer per category).

NFR-5.2. The module SHALL NOT depend on any libraries beyond what the project already uses (Python stdlib + existing dependencies). In particular, `urllib.robotparser` (stdlib) SHALL be used for robots.txt parsing.

NFR-5.3. The list of known AI user-agents (FR-2.2) SHALL be defined as a constant, making it straightforward to update as new AI crawlers emerge.

NFR-5.4. The llms.txt structural validation logic SHALL be straightforward to update as the llms.txt specification evolves.
