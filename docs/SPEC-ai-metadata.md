# BotAudit AI Metadata Detection Specification

## Key Words

The key words "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

---

## Background

The LLM Discoverability category (`SPEC-llms-txt.md`) currently evaluates three files: `robots.txt`, `llms.txt`, and `llms-full.txt`. These represent the first wave of AI-specific site infrastructure — crawl policies and LLM resource maps.

A second wave of AI metadata standards is emerging:

- **`ai.txt`** — A site-level plain-text file declaring AI interaction preferences, usage policies, and attribution requirements. It complements `robots.txt` (which controls access) with guidance on *how* AI systems should use a site's content.

- **`/.well-known/ai-plugin.json`** — OpenAI's plugin manifest format, designed to let AI assistants discover and interact with a site's API. Contains structured metadata including human- and model-facing descriptions, API schema references, authentication details, and contact information.

- **`/.well-known/agent.json`** — The Agent Protocol discovery file, enabling AI agents to discover a site's agent-compatible endpoints and capabilities.

These files signal that a site is actively prepared for AI interaction — not just passively crawlable, but intentionally structured for AI consumption. This specification extends the LLM Discoverability category to detect and evaluate these metadata files, redistributing the existing 100-point scoring budget to accommodate the new signals.

---

## Functional Requirements

### FR-1. Additional Fetches

FR-1.1. The tool SHALL attempt to fetch the following additional files from the origin of the provided URL:

| File | Path | Purpose |
|------|------|---------|
| ai.txt | `/ai.txt` | AI interaction policy and usage guidance |
| AI plugin manifest | `/.well-known/ai-plugin.json` | OpenAI-style plugin discovery manifest |
| Agent protocol manifest | `/.well-known/agent.json` | Agent Protocol endpoint discovery |

FR-1.2. These fetches SHALL be performed as separate HTTP GET requests, independent of the primary HTML fetch and the existing supplementary fetches (robots.txt, llms.txt, llms-full.txt).

FR-1.3. The tool SHALL use the same User-Agent, timeout, and redirect settings as the primary fetch.

FR-1.4. The tool SHALL treat a 404, 403, or any non-2xx response for any of these files as "not present" and continue analysis without error.

FR-1.5. The tool SHALL treat network errors (DNS failure, timeout, connection refused) for any of these fetches as "not present" and SHALL NOT fail the overall analysis.

FR-1.6. For `ai.txt`, the tool SHALL validate that the response Content-Type is text (e.g., `text/plain`). If the response is HTML or another non-text format, the tool SHALL treat the file as "not present."

FR-1.7. For `ai-plugin.json` and `agent.json`, the tool SHALL validate that the response Content-Type is JSON (e.g., `application/json`) or text. If the response is HTML, the tool SHALL treat the file as "not present."

FR-1.8. The tool SHOULD perform all new fetches concurrently with each other and with the existing supplementary fetches to minimize total latency.

FR-1.9. When `--skip-llm-discovery` is active, ALL supplementary fetches — including the new files introduced by this specification — SHALL be skipped.

### FR-2. ai.txt Analysis

FR-2.1. The tool SHALL treat `ai.txt` as a plain-text file containing AI interaction policies.

FR-2.2. The tool SHALL check that the file is non-empty and contains substantive content (more than 10 characters after trimming whitespace).

FR-2.3. The tool SHALL NOT perform deep structural analysis of `ai.txt`. Presence of a valid, non-empty text response is sufficient for detection.

FR-2.4. The tool MAY report the approximate size (line count) of `ai.txt` in findings.

### FR-3. ai-plugin.json Analysis

FR-3.1. The tool SHALL attempt to parse `/.well-known/ai-plugin.json` as JSON. If parsing fails, the tool SHALL treat the file as "not present."

FR-3.2. The tool SHALL validate the following fields in the parsed JSON:

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `schema_version` | Yes | string | Manifest schema version |
| `name_for_human` | Yes | string | Human-readable plugin name |
| `name_for_model` | Yes | string | Model-facing plugin identifier |
| `description_for_human` | Yes | string | Human-readable description |
| `description_for_model` | Yes | string | Model-facing description |
| `api` | No | object | API specification reference |
| `auth` | No | object | Authentication configuration |

FR-3.3. The manifest SHALL be considered **structurally valid** when all required fields (FR-3.2) are present and are non-empty strings.

FR-3.4. When the `api` field is present, the tool SHALL check for the presence of `api.type` and `api.url` sub-fields.

FR-3.5. The tool SHALL NOT fetch or validate any URLs referenced within the manifest (e.g., `api.url`, `logo_url`). Presence of the fields is sufficient.

### FR-4. agent.json Analysis

FR-4.1. The tool SHALL attempt to parse `/.well-known/agent.json` as JSON. If parsing fails, the tool SHALL treat the file as "not present."

FR-4.2. The tool SHALL check that the parsed JSON is a non-empty object (not an empty `{}`).

FR-4.3. The tool SHALL NOT enforce a specific schema for `agent.json`, as the Agent Protocol specification is still evolving. Presence of a valid, non-empty JSON object is sufficient.

FR-4.4. The tool MAY report the top-level keys found in `agent.json` in findings.

### FR-5. Revised Scoring

FR-5.1. The LLM Discoverability category SHALL retain a total possible score of 100 points.

FR-5.2. The scoring breakdown SHALL be revised as follows:

| Signal | Points | Condition | Change |
|--------|--------|-----------|--------|
| AI crawlers not blocked | 30 | robots.txt absent, or classification is `open` or `partial` | Unchanged |
| Explicit Allow for AI bots | 5 | At least one AI user-agent has an explicit `Allow` rule | Unchanged |
| Sitemap in robots.txt | 5 | `Sitemap:` directive present | Unchanged |
| llms.txt present | 15 | File exists and returns valid text | Was 20 |
| llms.txt valid structure | 5 | Has required H1 heading | Unchanged |
| llms.txt summary present | 5 | Blockquote with substantive content (>5 words) | Unchanged |
| llms.txt resource links | 5 | At least one H2 section with resource links | Was 10 |
| llms.txt markdown resources | 5 | One or more resource links point to `.md` files | Unchanged |
| llms-full.txt present | 5 | File exists and returns valid, non-empty text | Was 10 |
| botaudit not blocked | 5 | The tool's own user-agent is not blocked | Unchanged |
| ai.txt present | **5** | File exists and returns valid, non-empty text | **New** |
| AI metadata manifest present | **5** | At least one of `ai-plugin.json` or `agent.json` is present and valid JSON | **New** |
| AI metadata manifest valid | **5** | `ai-plugin.json` passes structural validation (FR-3.3) OR `agent.json` is a non-empty object (FR-4.2) | **New** |
| **Total** | **100** | | |

FR-5.3. The "AI metadata manifest present" signal (5 points) SHALL be awarded when at least one of `ai-plugin.json` or `agent.json` returns a valid JSON response. Having both files present SHALL NOT award additional points for this signal.

FR-5.4. The "AI metadata manifest valid" signal (5 points) SHALL be awarded when at least one manifest passes its validation checks: `ai-plugin.json` is structurally valid per FR-3.3, OR `agent.json` is a non-empty JSON object per FR-4.2. Both passing SHALL NOT award additional points for this signal.

FR-5.5. When both manifests are present and valid, the findings SHALL list both files.

FR-5.6. The existing rule that llms-full.txt only scores when llms.txt is also present (`SPEC-llms-txt` FR-5.4) SHALL remain in effect.

FR-5.7. `ai.txt`, `ai-plugin.json`, and `agent.json` signals SHALL be awarded independently — they do not depend on the presence of llms.txt or each other.

FR-5.8. When robots.txt is classified as `restrictive`, the "AI crawlers not blocked" and "botaudit not blocked" signals SHALL continue to score 0 — capping the maximum category score at 65 (unchanged from `SPEC-llms-txt`).

FR-5.9. A site with no robots.txt and no other discovery files SHALL score 30 (the "not blocked" baseline, unchanged from `SPEC-llms-txt`).

### FR-6. Findings

FR-6.1. When `ai.txt` is present, the findings SHALL include: `ai.txt present ({N} lines).`

FR-6.2. When `ai.txt` is not present, the findings SHALL include: `No ai.txt file found.`

FR-6.3. When `ai-plugin.json` is present and structurally valid, the findings SHALL include: `ai-plugin.json present — valid plugin manifest (name: "{name_for_human}").`

FR-6.4. When `ai-plugin.json` is present but not structurally valid, the findings SHALL include: `ai-plugin.json present but missing required fields.`

FR-6.5. When `ai-plugin.json` is not present, the findings SHALL include: `No ai-plugin.json found.`

FR-6.6. When `agent.json` is present and is a non-empty JSON object, the findings SHALL include: `agent.json present.`

FR-6.7. When `agent.json` is not present, the findings SHALL include: `No agent.json found.`

### FR-7. Recommendations

FR-7.1. When `ai.txt` is absent, the recommendation engine SHOULD recommend creating a `/ai.txt` file as a `low` severity item.

FR-7.2. When neither `ai-plugin.json` nor `agent.json` is present, the recommendation engine MAY recommend creating an `ai-plugin.json` manifest as a `low` severity item for sites that expose an API.

FR-7.3. When `ai-plugin.json` is present but fails structural validation (FR-3.3), the recommendation engine SHALL recommend fixing the missing required fields as a `low` severity item, listing which fields are absent.

FR-7.4. AI metadata recommendations SHALL only be generated when the LLM Discoverability category score is below the recommendation threshold (consistent with existing behavior).

---

## Output

### FR-8. Output Format Integration

FR-8.1. The new findings and recommendations SHALL appear within the existing LLM Discoverability category section in all output formats (text, JSON, CSV, HTML).

FR-8.2. In JSON output, the `ai_metadata` sub-object SHALL be added to the LLM Discoverability result:

```json
{
  "llm_discoverability": {
    "robots": { "..." : "..." },
    "llms_txt": { "..." : "..." },
    "llms_full_txt": { "..." : "..." },
    "ai_metadata": {
      "ai_txt": {
        "present": true,
        "line_count": 15
      },
      "ai_plugin_json": {
        "present": true,
        "valid": true,
        "name_for_human": "Example Plugin",
        "name_for_model": "example",
        "has_api": true
      },
      "agent_json": {
        "present": false
      }
    }
  }
}
```

FR-8.3. The `ai_metadata` object SHALL always be present in JSON output when LLM Discoverability is active, even when all files are absent (all `present` fields will be `false`).

---

## Exit Codes

### FR-9. Exit Code Behavior

FR-9.1. The new metadata checks SHALL NOT alter exit code behavior. All exit code semantics defined in the base spec, `SPEC-batch.md`, and `SPEC-crawl.md` SHALL apply unchanged.

---

## Non-Functional Requirements

### NFR-1. Performance

NFR-1.1. The three additional fetches SHALL be performed concurrently with each other and with the existing supplementary fetches, for a maximum of six concurrent supplementary requests.

NFR-1.2. The total added latency for sites missing all three new files SHOULD be negligible — three concurrent non-2xx responses overlapping with existing fetches.

NFR-1.3. JSON parsing of manifest files SHALL be performed using Python's `json` module (stdlib). The tool SHALL NOT introduce new dependencies for parsing.

### NFR-2. Graceful Degradation

NFR-2.1. The tool SHALL produce a complete, valid report even when any or all new fetches fail.

NFR-2.2. The absence of `ai.txt`, `ai-plugin.json`, or `agent.json` SHALL NOT produce warnings or error output. These are expected conditions — adoption of these standards is nascent.

NFR-2.3. Malformed JSON in `ai-plugin.json` or `agent.json` SHALL be handled gracefully — treated as "not present" with no stack trace or error output.

### NFR-3. Backward Compatibility

NFR-3.1. The revised scoring (FR-5) changes point allocations for existing signals. Sites with no AI metadata files will see their LLM Discoverability score shift due to redistribution:

| Scenario | Old Score | New Score | Delta |
|----------|-----------|-----------|-------|
| No robots.txt, no llms.txt, no new files | 30 | 30 | 0 |
| Full llms.txt suite, no new files | 100 | 85 | -15 |
| Full llms.txt suite + all new files | — | 100 | — |

NFR-3.2. The overall grade impact of score changes SHALL be minimal due to the category's 10% weight. A 15-point reduction in LLM Discoverability (for sites with full llms.txt but no AI metadata) reduces the overall score by 1.5 points at most. Sites with no discovery files at all are unaffected.

NFR-3.3. No existing function signatures SHALL change. New parameters SHALL use keyword arguments with defaults that preserve current behavior.

### NFR-4. Maintainability

NFR-4.1. The AI metadata analysis logic SHALL be implemented within the existing `llm_discoverability.py` module, extending the current analyzer rather than creating a separate module.

NFR-4.2. New result dataclasses SHALL follow the same patterns as the existing `LlmsTxtResult` and `LlmsFullTxtResult` classes.

NFR-4.3. The list of required fields for `ai-plugin.json` (FR-3.2) SHALL be defined as a constant, making it straightforward to update as the manifest format evolves.

NFR-4.4. Fetching of the new files SHALL be added to the existing `fetch_discovery_files()` function, extending its return value while maintaining backward compatibility via keyword arguments or an expanded result type.

### NFR-5. Testability

NFR-5.1. Analysis functions for the new file types SHALL be testable as pure functions — given file content strings, they return result dataclasses. No HTTP requests, no side effects.

NFR-5.2. Tests SHALL verify that:

- `ai.txt` presence is correctly detected from non-empty text content.
- `ai.txt` is treated as "not present" when content is empty or whitespace-only.
- `ai.txt` is treated as "not present" when content is fewer than 10 characters.
- `ai-plugin.json` is correctly parsed and validated against required fields.
- Missing required fields in `ai-plugin.json` result in `valid: false`.
- Malformed JSON in `ai-plugin.json` is treated as "not present."
- `agent.json` is correctly detected as a non-empty JSON object.
- Empty JSON object `{}` in `agent.json` is treated as invalid.
- Malformed JSON in `agent.json` is treated as "not present."
- Scoring correctly awards points for each new signal independently.
- Scoring correctly handles combinations (some files present, others absent).
- Findings include appropriate messages for present and absent files.
- Recommendations are generated for absent or invalid files.
- HTML Content-Type responses are rejected for all new file types.

NFR-5.3. Integration tests SHALL verify that the new fetches are performed alongside existing supplementary fetches and that results propagate through the full pipeline (fetch → analyze → score → report).

---

## Data Model

### FR-10. Result Dataclasses

FR-10.1. The following new dataclasses SHALL be added to `llm_discoverability.py`:

```python
@dataclass
class AiTxtResult:
    """ai.txt detection result."""
    present: bool
    line_count: int  # 0 when not present

@dataclass
class AiPluginJsonResult:
    """/.well-known/ai-plugin.json analysis result."""
    present: bool
    valid: bool              # True when all required fields present
    name_for_human: str      # Empty when not present or invalid
    name_for_model: str      # Empty when not present or invalid
    has_api: bool            # api.type and api.url both present

@dataclass
class AgentJsonResult:
    """/.well-known/agent.json detection result."""
    present: bool            # Non-empty JSON object

@dataclass
class AIMetadataResult:
    """Combined AI metadata detection results."""
    ai_txt: AiTxtResult
    ai_plugin_json: AiPluginJsonResult
    agent_json: AgentJsonResult
```

FR-10.2. The existing `LLMDiscoverabilityResult` dataclass SHALL be extended with an `ai_metadata` field:

```python
@dataclass
class LLMDiscoverabilityResult:
    robots: RobotsTxtResult
    llms_txt: LlmsTxtResult
    llms_full_txt: LlmsFullTxtResult
    ai_metadata: AIMetadataResult  # NEW
```

FR-10.3. To maintain backward compatibility, the `ai_metadata` field SHALL default to a result with all files absent when not provided.

---

## CLI Interface Summary

No new CLI flags are introduced. The AI metadata checks are automatically included in the LLM Discoverability category and controlled by the existing `--skip-llm-discovery` flag.

```
botaudit https://example.com                      # Includes AI metadata checks
botaudit https://example.com --skip-llm-discovery  # Skips all LLM discovery including AI metadata
```
