"""Tests for gasclaw.kimigas.proxy."""

from __future__ import annotations

from gasclaw.kimigas.proxy import KIMI_ANTHROPIC_BASE_URL, build_claude_env


class TestBuildClaudeEnv:
    def test_contains_required_keys(self):
        env = build_claude_env("sk-test-key", config_dir="/tmp/claude-cfg")
        assert env["ANTHROPIC_BASE_URL"] == KIMI_ANTHROPIC_BASE_URL
        assert env["ANTHROPIC_API_KEY"] == "sk-test-key"
        assert env["CLAUDE_CONFIG_DIR"] == "/tmp/claude-cfg"
        assert env["DISABLE_COST_WARNINGS"] == "true"

    def test_key_injected_from_argument(self):
        env = build_claude_env("sk-specific-key")
        assert env["ANTHROPIC_API_KEY"] == "sk-specific-key"

    def test_default_config_dir(self):
        env = build_claude_env("sk-test")
        assert "CLAUDE_CONFIG_DIR" in env
        assert ".claude-kimigas" in env["CLAUDE_CONFIG_DIR"]

    def test_custom_config_dir(self):
        env = build_claude_env("sk-test", config_dir="/custom/path")
        assert env["CLAUDE_CONFIG_DIR"] == "/custom/path"

    def test_base_url_is_kimi(self):
        env = build_claude_env("sk-test")
        assert "kimi.com" in env["ANTHROPIC_BASE_URL"]
