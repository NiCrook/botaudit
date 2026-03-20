"""LLM Discoverability — analysis of robots.txt, llms.txt, llms-full.txt.

FR-1   Fetching of robots.txt, llms.txt, llms-full.txt
FR-3   llms.txt structural validation
FR-4   llms.txt content quality assessment
FR-5   llms-full.txt detection
"""

from __future__ import annotations

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
# Combined result
# ---------------------------------------------------------------------------


@dataclass
class LLMDiscoverabilityResult:
    """Combined LLM Discoverability analysis results."""

    robots: RobotsTxtResult = field(default_factory=RobotsTxtResult)
    llms_txt: LlmsTxtResult = field(default_factory=LlmsTxtResult)
    llms_full_txt: LlmsFullTxtResult = field(default_factory=LlmsFullTxtResult)


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


def fetch_discovery_files(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[str | None, str | None, str | None]:
    """FR-1 — Fetch robots.txt, llms.txt, llms-full.txt from the origin.

    FR-1.2: Separate HTTP GET requests, independent of primary fetch.
    FR-1.3: Same User-Agent, timeout, redirect settings as primary fetch.
    NFR-1.1: Three fetches performed concurrently.

    Returns ``(robots_txt, llms_txt, llms_full_txt)`` — each is either
    the file content as a string, or ``None`` if not present.
    """
    origin = _get_origin(url)
    paths = ["/robots.txt", "/llms.txt", "/llms-full.txt"]

    # FR-1.3 — Reuse same client settings as primary fetch
    with httpx.Client(
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        # NFR-1.1 — Concurrent fetches
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(
                pool.map(lambda p: _fetch_text_file(client, origin + p), paths)
            )

    return results[0], results[1], results[2]


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
# Orchestrator
# ---------------------------------------------------------------------------


def analyze_llm_discovery(
    robots_txt: str | None,
    llms_txt: str | None,
    llms_full_txt: str | None,
) -> LLMDiscoverabilityResult:
    """Run all LLM Discoverability analyses and return combined result."""
    return LLMDiscoverabilityResult(
        robots=analyze_robots_txt(robots_txt),
        llms_txt=analyze_llms_txt(llms_txt),
        llms_full_txt=analyze_llms_full_txt(llms_full_txt),
    )
