"""Tests for FR-2 — robots.txt analysis."""

import unittest

from botaudit.robots_analysis import (
    AI_USER_AGENTS,
    RobotsTxtResult,
    analyze_robots_txt,
    _is_agent_mentioned,
)


class TestAnalyzeRobotsTxt(unittest.TestCase):
    """FR-2 — robots.txt analysis."""

    # --- FR-1.4 / FR-2.4: Not present ---

    def test_none_content_returns_not_present(self):
        result = analyze_robots_txt(None)
        self.assertFalse(result.present)
        self.assertEqual(result.classification, "open")
        self.assertEqual(result.agent_statuses, {})
        self.assertEqual(result.blocked_agents, [])
        self.assertFalse(result.has_sitemap)

    # --- FR-2.4: Classification "open" ---

    def test_empty_robots_txt_is_open(self):
        result = analyze_robots_txt("")
        self.assertTrue(result.present)
        self.assertEqual(result.classification, "open")
        self.assertEqual(len(result.blocked_agents), 0)

    def test_unrelated_rules_is_open(self):
        content = "User-agent: Googlebot\nDisallow: /private/\n"
        result = analyze_robots_txt(content)
        self.assertEqual(result.classification, "open")
        self.assertEqual(len(result.blocked_agents), 0)

    def test_allow_all_is_open(self):
        content = "User-agent: *\nAllow: /\n"
        result = analyze_robots_txt(content)
        self.assertEqual(result.classification, "open")

    # --- FR-2.4: Classification "partial" ---

    def test_block_one_ai_agent_is_partial(self):
        content = "User-agent: GPTBot\nDisallow: /\n"
        result = analyze_robots_txt(content)
        self.assertEqual(result.classification, "partial")
        self.assertIn("GPTBot", result.blocked_agents)
        self.assertEqual(result.agent_statuses["GPTBot"], "blocked")

    def test_block_some_ai_agents_is_partial(self):
        content = (
            "User-agent: GPTBot\nDisallow: /\n\n"
            "User-agent: ClaudeBot\nDisallow: /\n"
        )
        result = analyze_robots_txt(content)
        self.assertEqual(result.classification, "partial")
        self.assertIn("GPTBot", result.blocked_agents)
        self.assertIn("ClaudeBot", result.blocked_agents)
        self.assertEqual(len(result.blocked_agents), 2)

    # --- FR-2.4: Classification "restrictive" ---

    def test_block_all_ai_agents_is_restrictive(self):
        content = "User-agent: *\nDisallow: /\n"
        result = analyze_robots_txt(content)
        self.assertEqual(result.classification, "restrictive")
        self.assertEqual(len(result.blocked_agents), len(AI_USER_AGENTS))

    def test_block_each_agent_individually_is_restrictive(self):
        lines = []
        for agent in AI_USER_AGENTS:
            lines.append(f"User-agent: {agent}")
            lines.append("Disallow: /")
            lines.append("")
        content = "\n".join(lines)
        result = analyze_robots_txt(content)
        self.assertEqual(result.classification, "restrictive")
        self.assertEqual(len(result.blocked_agents), len(AI_USER_AGENTS))

    # --- FR-2.3: Per-agent status ---

    def test_explicitly_allowed_agent(self):
        content = "User-agent: GPTBot\nAllow: /\n"
        result = analyze_robots_txt(content)
        self.assertEqual(result.agent_statuses["GPTBot"], "allowed")

    def test_not_mentioned_agent(self):
        content = "User-agent: Googlebot\nDisallow: /private/\n"
        result = analyze_robots_txt(content)
        self.assertEqual(result.agent_statuses["GPTBot"], "not_mentioned")
        self.assertEqual(result.agent_statuses["ClaudeBot"], "not_mentioned")

    def test_blocked_by_wildcard(self):
        """Agent blocked by User-agent: * is still 'blocked', not 'not_mentioned'."""
        content = "User-agent: *\nDisallow: /\n"
        result = analyze_robots_txt(content)
        for agent in AI_USER_AGENTS:
            self.assertEqual(result.agent_statuses[agent], "blocked")

    def test_mixed_statuses(self):
        content = (
            "User-agent: GPTBot\nDisallow: /\n\n"
            "User-agent: ClaudeBot\nAllow: /\n"
        )
        result = analyze_robots_txt(content)
        self.assertEqual(result.agent_statuses["GPTBot"], "blocked")
        self.assertEqual(result.agent_statuses["ClaudeBot"], "allowed")
        self.assertEqual(result.agent_statuses["CCBot"], "not_mentioned")

    def test_wildcard_block_with_specific_allow(self):
        """Specific Allow overrides wildcard Disallow."""
        content = (
            "User-agent: *\nDisallow: /\n\n"
            "User-agent: ClaudeBot\nAllow: /\n"
        )
        result = analyze_robots_txt(content)
        self.assertEqual(result.agent_statuses["ClaudeBot"], "allowed")
        self.assertEqual(result.agent_statuses["GPTBot"], "blocked")
        self.assertEqual(result.classification, "partial")

    # --- FR-2.2: All 9 AI user-agents checked ---

    def test_all_ai_agents_checked(self):
        result = analyze_robots_txt("")
        self.assertEqual(len(result.agent_statuses), 9)
        expected = {
            "GPTBot", "ChatGPT-User", "Google-Extended", "ClaudeBot",
            "anthropic-ai", "PerplexityBot", "Bytespider", "CCBot",
            "cohere-ai",
        }
        self.assertEqual(set(result.agent_statuses.keys()), expected)

    # --- FR-2.6: Sitemap directive ---

    def test_sitemap_present(self):
        content = (
            "User-agent: *\nAllow: /\n\n"
            "Sitemap: https://example.com/sitemap.xml\n"
        )
        result = analyze_robots_txt(content)
        self.assertTrue(result.has_sitemap)

    def test_sitemap_absent(self):
        content = "User-agent: *\nAllow: /\n"
        result = analyze_robots_txt(content)
        self.assertFalse(result.has_sitemap)

    def test_multiple_sitemaps(self):
        content = (
            "Sitemap: https://example.com/sitemap1.xml\n"
            "Sitemap: https://example.com/sitemap2.xml\n"
        )
        result = analyze_robots_txt(content)
        self.assertTrue(result.has_sitemap)

    # --- Edge cases / NFR-2.3 ---

    def test_malformed_robots_txt_does_not_crash(self):
        content = "This is not a valid robots.txt\nfoo bar baz\n!!!"
        result = analyze_robots_txt(content)
        self.assertTrue(result.present)
        self.assertEqual(result.classification, "open")

    def test_case_insensitive_user_agent_matching(self):
        content = "User-Agent: gptbot\nDisallow: /\n"
        result = analyze_robots_txt(content)
        self.assertEqual(result.agent_statuses["GPTBot"], "blocked")

    def test_partial_path_disallow_does_not_block(self):
        """Disallow: /private/ does not block root access."""
        content = "User-agent: GPTBot\nDisallow: /private/\n"
        result = analyze_robots_txt(content)
        # GPTBot is mentioned but not fully blocked (only /private/ is blocked)
        self.assertEqual(result.agent_statuses["GPTBot"], "allowed")
        self.assertNotIn("GPTBot", result.blocked_agents)

    def test_comments_ignored(self):
        content = (
            "# Block AI crawlers\n"
            "User-agent: GPTBot\n"
            "Disallow: /\n"
        )
        result = analyze_robots_txt(content)
        self.assertEqual(result.agent_statuses["GPTBot"], "blocked")


class TestIsAgentMentioned(unittest.TestCase):
    """Helper function for detecting explicit user-agent lines."""

    def test_exact_match(self):
        self.assertTrue(_is_agent_mentioned("User-agent: GPTBot\n", "GPTBot"))

    def test_case_insensitive(self):
        self.assertTrue(_is_agent_mentioned("User-agent: gptbot\n", "GPTBot"))

    def test_not_present(self):
        self.assertFalse(_is_agent_mentioned("User-agent: Googlebot\n", "GPTBot"))

    def test_partial_name_no_match(self):
        self.assertFalse(_is_agent_mentioned("User-agent: GPTBot-Extended\n", "GPTBot"))

    def test_whitespace_handling(self):
        self.assertTrue(_is_agent_mentioned("  User-agent:  GPTBot  \n", "GPTBot"))
