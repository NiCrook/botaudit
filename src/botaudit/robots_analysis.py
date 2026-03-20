"""FR-2 — robots.txt analysis for AI crawler access policies.

Parses robots.txt per RFC 9309 using urllib.robotparser (FR-2.5)
and evaluates AI user-agent access policies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.robotparser import RobotFileParser

# FR-2.2 / NFR-5.3 — Known AI user-agents, defined as a constant.
AI_USER_AGENTS: dict[str, str] = {
    "GPTBot": "OpenAI",
    "ChatGPT-User": "OpenAI",
    "Google-Extended": "Google",
    "ClaudeBot": "Anthropic",
    "anthropic-ai": "Anthropic",
    "PerplexityBot": "Perplexity",
    "Bytespider": "ByteDance",
    "CCBot": "Common Crawl",
    "cohere-ai": "Cohere",
}


@dataclass
class RobotsTxtResult:
    """Result of robots.txt analysis for AI crawler access."""

    present: bool = False
    classification: str = "open"  # "open" | "partial" | "restrictive"
    agent_statuses: dict[str, str] = field(default_factory=dict)
    # ^ agent name -> "allowed" | "blocked" | "not_mentioned"
    blocked_agents: list[str] = field(default_factory=list)
    has_sitemap: bool = False
    tool_allowed: bool = True  # Whether the botaudit user-agent is permitted


def _is_agent_mentioned(content: str, agent: str) -> bool:
    """Check if a user-agent is explicitly named in a User-agent: line."""
    agent_lower = agent.lower()
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("user-agent:"):
            ua = stripped.split(":", 1)[1].strip().lower()
            if ua == agent_lower:
                return True
    return False


def analyze_robots_txt(content: str | None) -> RobotsTxtResult:
    """FR-2 — Analyze robots.txt for AI crawler access policies.

    Args:
        content: Raw text content of robots.txt, or None if not present.

    Returns:
        RobotsTxtResult with classification and per-agent statuses.
    """
    # FR-1.4 / FR-2.4 — Not present means "open"
    if content is None:
        return RobotsTxtResult(present=False, classification="open")

    # FR-2.1 / FR-2.5 — Parse with stdlib robotparser
    rp = RobotFileParser()
    rp.parse(content.splitlines())

    # FR-2.2 / FR-2.3 — Determine status for each AI user-agent
    agent_statuses: dict[str, str] = {}
    blocked: list[str] = []

    for agent in AI_USER_AGENTS:
        can_crawl = rp.can_fetch(agent, "/")
        mentioned = _is_agent_mentioned(content, agent)

        if not can_crawl:
            agent_statuses[agent] = "blocked"
            blocked.append(agent)
        elif mentioned:
            agent_statuses[agent] = "allowed"
        else:
            agent_statuses[agent] = "not_mentioned"

    # FR-2.4 — Summary classification
    if len(blocked) == len(AI_USER_AGENTS):
        classification = "restrictive"
    elif len(blocked) > 0:
        classification = "partial"
    else:
        classification = "open"

    # FR-2.6 — Sitemap directive
    sitemaps = rp.site_maps()
    has_sitemap = sitemaps is not None and len(sitemaps) > 0

    # FR-6.2 — Check tool's own user-agent
    tool_allowed = rp.can_fetch("botaudit", "/")

    return RobotsTxtResult(
        present=True,
        classification=classification,
        agent_statuses=agent_statuses,
        blocked_agents=blocked,
        has_sitemap=has_sitemap,
        tool_allowed=tool_allowed,
    )
