"""Unit tests for user-context scrubbing in tools/capture_prompt.py."""

from __future__ import annotations

import pathlib
import unittest

from tools import capture_prompt


class PromptScrubbingTests(unittest.TestCase):
    def test_withhold_rules_replaces_rule_blocks(self) -> None:
        raw = "header\n<RULE[user_global]>\nsecret rule\n</RULE[user_global]>\nfooter"
        scrubbed = capture_prompt.withhold_user_context("user_rules", raw)
        self.assertEqual(scrubbed, "header\n[dynamic: your AGENTS.md / rules]\nfooter")

    def test_withhold_skills_keeps_builtin_and_scrubs_user_skills(self) -> None:
        raw = (
            "Available skills:\n"
            "- antigravity-guide (<appDataDir>/builtin/skills/antigravity_guide/SKILL.md): built-in.\n"
            "- private-skill (<home>/.gemini/config/skills/private-skill/SKILL.md): personal.\n"
            "- swarm (<appDataDir>/builtin/skills/native_swarm/SKILL.md): built-in.\n"
        )
        scrubbed = capture_prompt.withhold_user_context("skills", raw)
        self.assertIn("antigravity-guide (<appDataDir>/builtin/skills/", scrubbed)
        self.assertIn("swarm (<appDataDir>/builtin/skills/", scrubbed)
        self.assertNotIn("private-skill", scrubbed)
        self.assertIn(capture_prompt.USER_SKILLS_MARK, scrubbed)

    def test_withhold_mcp_servers_hides_configured_servers(self) -> None:
        raw = (
            "Format:\n```\n# <serverName>\nEager:\n<toolName>\nLazy:\n<toolName>\n```\n"
            "# SecretInternalMCP\nLazy:\nsecret_tool\n"
        )
        scrubbed = capture_prompt.withhold_user_context("mcp_servers", raw)
        self.assertNotIn("SecretInternalMCP", scrubbed)
        self.assertIn(capture_prompt.MCP_SERVERS_MARK, scrubbed)

    def test_normalize_replaces_home_and_workspace(self) -> None:
        ws = pathlib.Path("/tmp/agy-test-ws")
        home = str(capture_prompt.HOME)
        raw = f"ws={ws} home={home}/foo The current local time is: 2026-11-16T10:00:00+08:00"
        # Note: normalize replaces workspace before home.
        norm = capture_prompt.normalize(raw, ws)
        self.assertNotIn(home, norm)
        self.assertIn("<workspace>", norm)
        self.assertIn("<home>/foo", norm)
        self.assertIn("The current local time is: <local-time>", norm)


if __name__ == "__main__":
    unittest.main()
