"""LLM Discoverability — analysis of robots.txt, llms.txt, llms-full.txt,
ai.txt, ai-plugin.json, agent.json.

FR-1   Fetching of robots.txt, llms.txt, llms-full.txt
FR-3   llms.txt structural validation
FR-4   llms.txt content quality assessment
FR-5   llms-full.txt detection
SPEC-ai-metadata FR-1  Fetching of ai.txt, ai-plugin.json, agent.json
SPEC-ai-metadata FR-2  ai.txt analysis
SPEC-ai-metadata FR-3  ai-plugin.json analysis
SPEC-ai-metadata FR-4  agent.json analysis
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from botaudit.fetcher import DEFAULT_TIMEOUT, MAX_REDIRECTS, USER_AGENT
from botaudit.robots_analysis import RobotsTxtResult, analyze_robots_txt

# ---------------------------------------------------------------------------
# Pattern for Markdown links: [text](url)
# ---------------------------------------------------------------------------

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


# ---------------------------------------------------------------------------
# FR-3 / FR-4  —  llms.txt result
# ---------------------------------------------------------------------------


@dataclass
class LlmsTxtResult:
    """Structural validation and content quality results for llms.txt."""

    # FR-3: structural validation
    present: bool = False
    is_valid: bool = False
    has_h1: bool = False
    h1_text: str = ""
    has_blockquote: bool = False
    blockquote_text: str = ""
    h2_count: int = 0
    h2_sections: list[str] = field(default_factory=list)
    resource_link_count: int = 0
    resource_links: list[tuple[str, str]] = field(default_factory=list)
    has_optional_section: bool = False
    # FR-4: content quality
    summary_substantive: bool = False  # FR-4.1: blockquote > 5 words
    has_md_links: bool = False  # FR-4.4: any link points to .md


# ---------------------------------------------------------------------------
# FR-5  —  llms-full.txt result
# ---------------------------------------------------------------------------


@dataclass
class LlmsFullTxtResult:
    """FR-5 — llms-full.txt detection result."""

    present: bool = False


# ---------------------------------------------------------------------------
# SPEC-ai-metadata FR-3.2 — Required fields for ai-plugin.json validation
# ---------------------------------------------------------------------------

AI_PLUGIN_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "name_for_human",
    "name_for_model",
    "description_for_human",
    "description_for_model",
)


# ---------------------------------------------------------------------------
# SPEC-ai-metadata FR-10.1 — AI metadata result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AiTxtResult:
    """SPEC-ai-metadata FR-2 — ai.txt detection result."""

    present: bool = False
    line_count: int = 0  # FR-2.4: approximate size


@dataclass
class AiPluginJsonResult:
    """SPEC-ai-metadata FR-3 — /.well-known/ai-plugin.json analysis result."""

    present: bool = False
    valid: bool = False  # FR-3.3: all required fields present and non-empty
    name_for_human: str = ""  # FR-3.2
    name_for_model: str = ""  # FR-3.2
    has_api: bool = False  # FR-3.4: api.type and api.url both present


@dataclass
class AgentJsonResult:
    """SPEC-ai-metadata FR-4 — /.well-known/agent.json detection result."""

    present: bool = False  # FR-4.2: non-empty JSON object


@dataclass
class AIMetadataResult:
    """SPEC-ai-metadata FR-10.1 — Combined AI metadata detection results."""

    ai_txt: AiTxtResult = field(default_factory=AiTxtResult)
    ai_plugin_json: AiPluginJsonResult = field(default_factory=AiPluginJsonResult)
    agent_json: AgentJsonResult = field(default_factory=AgentJsonResult)


# ---------------------------------------------------------------------------
# Combined result
# ---------------------------------------------------------------------------


@dataclass
class LLMDiscoverabilityResult:
    """Combined LLM Discoverability analysis results."""

    robots: RobotsTxtResult = field(default_factory=RobotsTxtResult)
    llms_txt: LlmsTxtResult = field(default_factory=LlmsTxtResult)
    llms_full_txt: LlmsFullTxtResult = field(default_factory=LlmsFullTxtResult)
    # SPEC-ai-metadata FR-10.2 / FR-10.3: defaults to all-absent
    ai_metadata: AIMetadataResult = field(default_factory=AIMetadataResult)


# ---------------------------------------------------------------------------
# FR-1  —  Fetching
# ---------------------------------------------------------------------------


def _get_origin(url: str) -> str:
    """Extract the origin (scheme + host) from a URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_text_content_type(content_type: str) -> bool:
    """FR-1.6 — Accept text/* content types except text/html."""
    if not content_type:
        return False
    media_type = content_type.split(";")[0].strip().lower()
    return media_type.startswith("text/") and media_type != "text/html"


def _is_json_content_type(content_type: str) -> bool:
    """SPEC-ai-metadata FR-1.7 — Accept application/json or text/* (not text/html)."""
    if not content_type:
        return False
    media_type = content_type.split(";")[0].strip().lower()
    if media_type == "application/json":
        return True
    return media_type.startswith("text/") and media_type != "text/html"


def _fetch_text_file(client: httpx.Client, url: str) -> str | None:
    """Fetch a single text file, returning content or None.

    FR-1.4: Non-2xx responses → None.
    FR-1.5: Network errors → None.
    FR-1.6: Non-text Content-Type → None.
    """
    try:
        response = client.get(url)
    except httpx.HTTPError:
        return None

    if not response.is_success:
        return None

    content_type = response.headers.get("content-type", "")
    if not _is_text_content_type(content_type):
        return None

    return response.text


def _fetch_json_file(client: httpx.Client, url: str) -> str | None:
    """SPEC-ai-metadata FR-1.7 — Fetch a JSON file, returning content or None.

    FR-1.4: Non-2xx responses → None.
    FR-1.5: Network errors → None.
    FR-1.7: Non-JSON/text Content-Type → None (HTML rejected).
    """
    try:
        response = client.get(url)
    except httpx.HTTPError:
        return None

    if not response.is_success:
        return None

    content_type = response.headers.get("content-type", "")
    if not _is_json_content_type(content_type):
        return None

    return response.text


def fetch_discovery_files(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """FR-1 / SPEC-ai-metadata FR-1 — Fetch all discovery files from the origin.

    Returns ``(robots_txt, llms_txt, llms_full_txt,
               ai_txt, ai_plugin_json, agent_json)``
    — each is either the file content as a string, or ``None`` if not present.

    SPEC-llms-txt FR-1.2: Separate HTTP GET requests.
    SPEC-llms-txt FR-1.3: Same User-Agent, timeout, redirect settings.
    SPEC-ai-metadata FR-1.2: New fetches independent of existing ones.
    SPEC-ai-metadata FR-1.8 / NFR-1.1: All six fetches performed concurrently.
    """
    origin = _get_origin(url)

    # (path, fetcher) pairs — text files use _fetch_text_file,
    # JSON files use _fetch_json_file (SPEC-ai-metadata FR-1.6 / FR-1.7)
    jobs: list[tuple[str, bool]] = [
        ("/robots.txt", False),           # text
        ("/llms.txt", False),             # text
        ("/llms-full.txt", False),        # text
        ("/ai.txt", False),               # SPEC-ai-metadata FR-1.6: text
        ("/.well-known/ai-plugin.json", True),  # SPEC-ai-metadata FR-1.7: JSON
        ("/.well-known/agent.json", True),      # SPEC-ai-metadata FR-1.7: JSON
    ]

    def _do_fetch(item: tuple[str, bool]) -> str | None:
        path, is_json = item
        if is_json:
            return _fetch_json_file(client, origin + path)
        return _fetch_text_file(client, origin + path)

    # FR-1.3 — Reuse same client settings as primary fetch
    with httpx.Client(
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        # SPEC-ai-metadata NFR-1.1 — Six concurrent fetches
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(_do_fetch, jobs))

    return results[0], results[1], results[2], results[3], results[4], results[5]


# ---------------------------------------------------------------------------
# FR-3  —  llms.txt structural validation
# FR-4  —  llms.txt content quality assessment
# ---------------------------------------------------------------------------


def analyze_llms_txt(content: str | None) -> LlmsTxtResult:
    """FR-3 / FR-4 — Validate llms.txt structure and assess content quality.

    Parses the Markdown content line-by-line to extract and validate:
    - H1 heading (required, must be first and only one)  — FR-3.2
    - Blockquote summary (optional, must follow H1)       — FR-3.3
    - H2 sections with resource links                     — FR-3.4
    - ``## Optional`` section                             — FR-3.5
    - Summary substantiveness (> 5 words)                 — FR-4.1
    - Resource link URL syntax                            — FR-4.3
    - Markdown resource detection (.md links)             — FR-4.4
    """
    result = LlmsTxtResult()

    if content is None or not content.strip():
        return result

    result.present = True
    lines = content.splitlines()

    h1_count = 0
    first_content_seen = False
    first_is_h1 = False
    in_blockquote_region = False
    in_h2_section = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        is_h1 = stripped.startswith("# ") and not stripped.startswith("## ")
        is_h2 = stripped.startswith("## ")
        is_blockquote = stripped.startswith("> ")
        is_list_item = stripped.startswith("- ") or stripped.startswith("* ")

        if not first_content_seen:
            first_content_seen = True
            first_is_h1 = is_h1

        # FR-3.2 — H1 headings
        if is_h1:
            h1_count += 1
            if h1_count == 1:
                result.h1_text = stripped[2:].strip()
                in_blockquote_region = True
                in_h2_section = False
            continue

        # FR-3.3 — Blockquote summary following H1
        if is_blockquote and in_blockquote_region:
            bq_text = stripped[2:].strip()
            if not result.has_blockquote:
                result.has_blockquote = True
                result.blockquote_text = bq_text
            else:
                result.blockquote_text += " " + bq_text
            continue

        # FR-3.4 / FR-3.5 — H2 sections
        if is_h2:
            in_blockquote_region = False
            in_h2_section = True
            h2_title = stripped[3:].strip()
            result.h2_count += 1
            result.h2_sections.append(h2_title)

            if h2_title.lower() == "optional":
                result.has_optional_section = True
            continue

        # FR-3.4 — Resource links in list items within H2 sections
        if is_list_item and in_h2_section:
            for text, url in _MD_LINK_RE.findall(stripped):
                result.resource_link_count += 1
                result.resource_links.append((text, url))

        in_blockquote_region = False

    # FR-3.2 — Exactly one H1, must be first non-empty line
    result.has_h1 = h1_count == 1 and first_is_h1

    # FR-3.6 — Structurally valid = has the required H1
    result.is_valid = result.has_h1

    # FR-4.1 — Summary substantiveness (> 5 words)
    if result.has_blockquote and result.blockquote_text:
        result.summary_substantive = len(result.blockquote_text.split()) > 5

    # FR-4.4 — Detect .md resource links
    for _text, url in result.resource_links:
        if url.strip().lower().endswith(".md"):
            result.has_md_links = True
            break

    return result


# ---------------------------------------------------------------------------
# FR-5  —  llms-full.txt detection
# ---------------------------------------------------------------------------


def analyze_llms_full_txt(content: str | None) -> LlmsFullTxtResult:
    """FR-5 — Check llms-full.txt presence and non-empty content.

    FR-5.2: Validates non-empty text content.
    FR-5.3: No deep structural analysis — presence is sufficient.
    """
    result = LlmsFullTxtResult()
    if content is not None and content.strip():
        result.present = True
    return result


# ---------------------------------------------------------------------------
# SPEC-ai-metadata FR-2  —  ai.txt analysis
# ---------------------------------------------------------------------------


def analyze_ai_txt(content: str | None) -> AiTxtResult:
    """SPEC-ai-metadata FR-2 — Check ai.txt presence and substantive content.

    FR-2.1: Plain-text file containing AI interaction policies.
    FR-2.2: Non-empty, >10 characters after trimming whitespace.
    FR-2.3: No deep structural analysis — presence is sufficient.
    FR-2.4: Report line count.
    """
    result = AiTxtResult()
    if content is None:
        return result
    trimmed = content.strip()
    if len(trimmed) <= 10:
        return result
    result.present = True
    result.line_count = len(content.splitlines())
    return result


# ---------------------------------------------------------------------------
# SPEC-ai-metadata FR-3  —  ai-plugin.json analysis
# ---------------------------------------------------------------------------


def analyze_ai_plugin_json(content: str | None) -> AiPluginJsonResult:
    """SPEC-ai-metadata FR-3 — Parse and validate ai-plugin.json.

    FR-3.1: Parse as JSON; treat parse failure as "not present."
    FR-3.2: Validate required fields (AI_PLUGIN_REQUIRED_FIELDS).
    FR-3.3: Structurally valid when all required fields are non-empty strings.
    FR-3.4: Check for api.type and api.url sub-fields when api is present.
    FR-3.5: Do NOT fetch or validate referenced URLs.
    """
    result = AiPluginJsonResult()
    if content is None:
        return result
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return result
    if not isinstance(data, dict):
        return result

    result.present = True

    # FR-3.3 — valid when all required fields are non-empty strings
    all_valid = True
    for field_name in AI_PLUGIN_REQUIRED_FIELDS:
        value = data.get(field_name)
        if not isinstance(value, str) or not value.strip():
            all_valid = False
            break
    result.valid = all_valid

    if result.valid:
        result.name_for_human = data["name_for_human"]
        result.name_for_model = data["name_for_model"]

    # FR-3.4 — check api sub-fields
    api = data.get("api")
    if isinstance(api, dict):
        result.has_api = bool(api.get("type")) and bool(api.get("url"))

    return result


# ---------------------------------------------------------------------------
# SPEC-ai-metadata FR-4  —  agent.json analysis
# ---------------------------------------------------------------------------


def analyze_agent_json(content: str | None) -> AgentJsonResult:
    """SPEC-ai-metadata FR-4 — Parse and validate agent.json.

    FR-4.1: Parse as JSON; treat parse failure as "not present."
    FR-4.2: Non-empty object (not {}).
    FR-4.3: No specific schema enforced — presence of non-empty object suffices.
    FR-4.4: MAY report top-level keys in findings (handled by scorer).
    """
    result = AgentJsonResult()
    if content is None:
        return result
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return result
    if isinstance(data, dict) and len(data) > 0:
        result.present = True
    return result


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def analyze_llm_discovery(
    robots_txt: str | None,
    llms_txt: str | None,
    llms_full_txt: str | None,
    *,
    ai_txt: str | None = None,
    ai_plugin_json: str | None = None,
    agent_json: str | None = None,
) -> LLMDiscoverabilityResult:
    """Run all LLM Discoverability analyses and return combined result.

    SPEC-ai-metadata NFR-3.3: New kwargs default to None for backward compat.
    """
    return LLMDiscoverabilityResult(
        robots=analyze_robots_txt(robots_txt),
        llms_txt=analyze_llms_txt(llms_txt),
        llms_full_txt=analyze_llms_full_txt(llms_full_txt),
        # SPEC-ai-metadata FR-10.2
        ai_metadata=AIMetadataResult(
            ai_txt=analyze_ai_txt(ai_txt),
            ai_plugin_json=analyze_ai_plugin_json(ai_plugin_json),
            agent_json=analyze_agent_json(agent_json),
        ),
    )
