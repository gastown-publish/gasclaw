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

    def test_empty_string_config_dir_uses_default(self):
        """Empty string config_dir falls back to default."""
        env = build_claude_env("sk-test", config_dir="")
        # Empty string is falsy, so default is used
        assert ".claude-kimigas" in env["CLAUDE_CONFIG_DIR"]

    def test_handles_special_chars_in_key(self):
        """API keys with special characters are handled correctly."""
        special_key = "sk-key-with-dash_and_underscore.123"
        env = build_claude_env(special_key)
        assert env["ANTHROPIC_API_KEY"] == special_key

    def test_config_dir_with_trailing_slash(self):
        """Config dir with trailing slash is preserved."""
        env = build_claude_env("sk-test", config_dir="/tmp/claude/")
        assert env["CLAUDE_CONFIG_DIR"] == "/tmp/claude/"
