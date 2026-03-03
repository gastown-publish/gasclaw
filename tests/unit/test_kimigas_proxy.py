"""Tests for gasclaw.kimigas.proxy."""

from __future__ import annotations

import json

from gasclaw.kimigas.proxy import KIMI_ANTHROPIC_BASE_URL, build_claude_env, write_claude_config


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


class TestWriteClaudeConfig:
    def test_creates_config_dir(self, tmp_path):
        cfg_dir = tmp_path / "claude-cfg"
        result = write_claude_config("sk-kimi-12345678901234567890", config_dir=str(cfg_dir))
        assert result == cfg_dir
        assert cfg_dir.is_dir()

    def test_writes_credentials_file(self, tmp_path):
        cfg_dir = tmp_path / "claude-cfg"
        write_claude_config("sk-kimi-12345678901234567890", config_dir=str(cfg_dir))
        creds = json.loads((cfg_dir / ".credentials.json").read_text())
        assert creds == {}

    def test_writes_claude_json_with_bypass(self, tmp_path):
        cfg_dir = tmp_path / "claude-cfg"
        write_claude_config("sk-kimi-12345678901234567890", config_dir=str(cfg_dir))
        data = json.loads((cfg_dir / ".claude.json").read_text())
        assert data["hasCompletedOnboarding"] is True
        assert data["bypassPermissionsModeAccepted"] is True

    def test_fingerprint_is_last_20_chars(self, tmp_path):
        cfg_dir = tmp_path / "claude-cfg"
        key = "sk-kimi-ABCDEF12345678901234567890"
        write_claude_config(key, config_dir=str(cfg_dir))
        data = json.loads((cfg_dir / ".claude.json").read_text())
        approved = data["customApiKeyResponses"]["approved"]
        assert approved == [key[-20:]]

    def test_short_key_uses_full_key_as_fingerprint(self, tmp_path):
        cfg_dir = tmp_path / "claude-cfg"
        write_claude_config("shortkey", config_dir=str(cfg_dir))
        data = json.loads((cfg_dir / ".claude.json").read_text())
        assert data["customApiKeyResponses"]["approved"] == ["shortkey"]

    def test_overwrites_existing_config(self, tmp_path):
        cfg_dir = tmp_path / "claude-cfg"
        cfg_dir.mkdir()
        (cfg_dir / ".claude.json").write_text('{"old": true}')
        write_claude_config("sk-kimi-12345678901234567890", config_dir=str(cfg_dir))
        data = json.loads((cfg_dir / ".claude.json").read_text())
        assert "old" not in data
        assert data["bypassPermissionsModeAccepted"] is True

    def test_default_config_dir_used(self, monkeypatch, tmp_path):
        monkeypatch.setattr("gasclaw.kimigas.proxy._DEFAULT_CONFIG_DIR", str(tmp_path / "default"))
        result = write_claude_config("sk-kimi-12345678901234567890")
        assert result == tmp_path / "default"
