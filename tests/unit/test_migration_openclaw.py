"""Tests for openclaw-launcher migration support."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from gasclaw.migration import (
    detect_openclaw_launcher_setup,
    migrate_openclaw_launcher,
)


class TestDetectOpenclawLauncherSetup:
    """Tests for detect_openclaw_launcher_setup function."""

    def test_detects_via_config_file(self, tmp_path, monkeypatch):
        """Detects openclaw-launcher via openclaw.json config file."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        # Create mock openclaw config
        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        config_file = openclaw_dir / "openclaw.json"
        config = {
            "agents": {
                "list": [{"id": "openclawmaster"}]
            },
            "channels": {
                "telegram": {
                    "enabled": True,
                    "botToken": "123:ABC",
                    "allowFrom": ["2045995148", "8606251619"]
                }
            },
            "gateway": {"port": 18790}
        }
        config_file.write_text(json.dumps(config))

        result = detect_openclaw_launcher_setup(openclaw_dir=openclaw_dir)

        assert result["detected"] is True
        assert result["source"] == "config_file"
        assert result["config_path"] == str(config_file)

    def test_returns_not_detected_when_gasclaw_configured(self, tmp_path, monkeypatch):
        """Returns not detected when gasclaw already configured."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-existing")

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        config_file = openclaw_dir / "openclaw.json"
        config_file.write_text(json.dumps({"agents": {"list": []}}))

        result = detect_openclaw_launcher_setup(openclaw_dir=openclaw_dir)

        assert result["detected"] is False
        assert result["reason"] == "gasclaw_config_already_exists"

    def test_returns_not_detected_when_no_config(self, tmp_path, monkeypatch):
        """Returns not detected when no openclaw.json found."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        # No config file created

        result = detect_openclaw_launcher_setup(openclaw_dir=openclaw_dir)

        assert result["detected"] is False
        assert result["reason"] == "no_openclaw_launcher_found"

    def test_handles_corrupted_config(self, tmp_path, monkeypatch):
        """Handles corrupted JSON config gracefully."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        config_file = openclaw_dir / "openclaw.json"
        config_file.write_text("not valid json {{{")

        result = detect_openclaw_launcher_setup(openclaw_dir=openclaw_dir)

        assert result["detected"] is False
        assert "couldn't read it" in result.get("message", "").lower()

    def test_uses_default_openclaw_dir(self, monkeypatch, tmp_path):
        """Uses default ~/.openclaw directory when none specified."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setattr(
            "gasclaw.migration.DEFAULT_OPENCLAW_DIR",
            tmp_path / ".openclaw"
        )

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        config_file = openclaw_dir / "openclaw.json"
        config_file.write_text(json.dumps({"agents": {"list": []}}))

        result = detect_openclaw_launcher_setup()

        assert result["detected"] is True

    def test_detects_launcher_dir(self, tmp_path, monkeypatch):
        """Detects via openclaw-launcher directory."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        # Override default openclaw dir to avoid detecting ~/.openclaw
        monkeypatch.setattr(
            "gasclaw.migration.DEFAULT_OPENCLAW_DIR",
            tmp_path / ".openclaw"  # This won't exist
        )

        launcher_dir = tmp_path / "openclaw-launcher"
        launcher_dir.mkdir()

        result = detect_openclaw_launcher_setup(launcher_dir=launcher_dir)

        assert result["detected"] is True
        assert result["source"] == "launcher_dir"


class TestMigrateOpenclawLauncher:
    """Tests for migrate_openclaw_launcher function."""

    def test_migrates_telegram_config(self, tmp_path, monkeypatch):
        """Migrates Telegram configuration from openclaw.json."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        agents_dir = openclaw_dir / "agents" / "agent1" / "agent"
        agents_dir.mkdir(parents=True)

        # Create auth-profiles.json for API key
        auth_file = agents_dir / "auth-profiles.json"
        auth_file.write_text(json.dumps({"default": {"api_key": "sk-kimi123"}}))

        config_file = openclaw_dir / "openclaw.json"
        config = {
            "agents": {"list": []},
            "channels": {
                "telegram": {
                    "enabled": True,
                    "botToken": "123:ABC",
                    "allowFrom": ["2045995148", "8606251619"]
                }
            },
            "gateway": {"port": 18790}
        }
        config_file.write_text(json.dumps(config))

        env_file = tmp_path / ".env"

        result = migrate_openclaw_launcher(
            openclaw_dir=openclaw_dir,
            env_file=env_file,
            interactive=False
        )

        assert result["success"] is True
        assert "TELEGRAM_BOT_TOKEN" in result["migrated_keys"]
        assert "TELEGRAM_OWNER_ID" in result["migrated_keys"]

        content = env_file.read_text()
        assert "TELEGRAM_BOT_TOKEN=123:ABC" in content
        assert "TELEGRAM_OWNER_ID=2045995148:8606251619" in content

    def test_migrates_agent_identity(self, tmp_path, monkeypatch):
        """Migrates agent identity (name, emoji)."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        agents_dir = openclaw_dir / "agents" / "agent1" / "agent"
        agents_dir.mkdir(parents=True)

        # Create auth-profiles.json for API key
        auth_file = agents_dir / "auth-profiles.json"
        auth_file.write_text(json.dumps({"default": {"api_key": "sk-kimi123"}}))

        config_file = openclaw_dir / "openclaw.json"
        config = {
            "agents": {
                "list": [{
                    "id": "openclawmaster",
                    "identity": {
                        "name": "OpenClawMaster",
                        "emoji": "🦾"
                    }
                }]
            },
            "channels": {"telegram": {"enabled": True, "botToken": "123", "allowFrom": ["123456"]}}
        }
        config_file.write_text(json.dumps(config))

        env_file = tmp_path / ".env"

        result = migrate_openclaw_launcher(
            openclaw_dir=openclaw_dir,
            env_file=env_file,
            interactive=False
        )

        assert result["success"] is True
        content = env_file.read_text()
        assert 'AGENT_NAME=OpenClawMaster' in content
        assert 'AGENT_EMOJI=🦾' in content

    def test_migrates_gateway_port(self, tmp_path, monkeypatch):
        """Migrates gateway port with warning about change."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        agents_dir = openclaw_dir / "agents" / "agent1" / "agent"
        agents_dir.mkdir(parents=True)

        # Create auth-profiles.json for API key
        auth_file = agents_dir / "auth-profiles.json"
        auth_file.write_text(json.dumps({"default": {"api_key": "sk-kimi123"}}))

        config_file = openclaw_dir / "openclaw.json"
        config = {
            "agents": {"list": []},
            "channels": {"telegram": {"enabled": True, "botToken": "123", "allowFrom": ["123456"]}},
            "gateway": {"port": 18790}
        }
        config_file.write_text(json.dumps(config))

        env_file = tmp_path / ".env"

        result = migrate_openclaw_launcher(
            openclaw_dir=openclaw_dir,
            env_file=env_file,
            interactive=False
        )

        assert result["success"] is True
        assert result["gateway_port_old"] == 18790
        assert result["gateway_port_new"] == 18789

        content = env_file.read_text()
        assert "GATEWAY_PORT=18789" in content

    def test_extracts_api_keys_from_auth_profiles(self, tmp_path, monkeypatch):
        """Extracts API keys from auth-profiles.json files."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        agents_dir = openclaw_dir / "agents" / "agent1" / "agent"
        agents_dir.mkdir(parents=True)

        # Create auth-profiles.json
        auth_file = agents_dir / "auth-profiles.json"
        auth_file.write_text(json.dumps({
            "default": {"api_key": "sk-kimi123"}
        }))

        # Create openclaw.json
        config_file = openclaw_dir / "openclaw.json"
        config_file.write_text(json.dumps({
            "agents": {"list": []},
            "channels": {"telegram": {"enabled": True, "botToken": "123", "allowFrom": ["123456"]}}
        }))

        env_file = tmp_path / ".env"

        result = migrate_openclaw_launcher(
            openclaw_dir=openclaw_dir,
            env_file=env_file,
            interactive=False
        )

        assert result["success"] is True
        assert "OPENCLAW_KIMI_KEY" in result["migrated_keys"]

        content = env_file.read_text()
        assert "OPENCLAW_KIMI_KEY=sk-kimi123" in content

    def test_generates_warnings(self, tmp_path, monkeypatch):
        """Generates appropriate warnings during migration."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        agents_dir = openclaw_dir / "agents" / "agent1" / "agent"
        agents_dir.mkdir(parents=True)

        # Create auth-profiles.json for API key
        auth_file = agents_dir / "auth-profiles.json"
        auth_file.write_text(json.dumps({"default": {"api_key": "sk-kimi123"}}))

        config_file = openclaw_dir / "openclaw.json"
        config = {
            "agents": {"list": []},
            "channels": {"telegram": {"enabled": True, "botToken": "123", "allowFrom": ["123456"]}},
            "gateway": {"port": 18790}
        }
        config_file.write_text(json.dumps(config))

        env_file = tmp_path / ".env"

        result = migrate_openclaw_launcher(
            openclaw_dir=openclaw_dir,
            env_file=env_file,
            interactive=False
        )

        assert result["success"] is True
        assert len(result["warnings"]) > 0
        # Should have warnings about port change and OPENCLAW_HOME
        warning_text = " ".join(result["warnings"])
        assert "18790" in warning_text
        assert "18789" in warning_text

    def test_handles_missing_required_config(self, tmp_path, monkeypatch):
        """Returns error when required config is missing."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        config_file = openclaw_dir / "openclaw.json"
        # Config without telegram bot token
        config_file.write_text(json.dumps({
            "agents": {"list": []},
            "channels": {}
        }))

        env_file = tmp_path / ".env"

        result = migrate_openclaw_launcher(
            openclaw_dir=openclaw_dir,
            env_file=env_file,
            interactive=False
        )

        assert result["success"] is False
        assert "error" in result

    def test_prompts_for_missing_keys_in_interactive_mode(self, tmp_path, monkeypatch):
        """Prompts for missing keys when interactive=True."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        openclaw_dir = tmp_path / ".openclaw"
        openclaw_dir.mkdir()
        config_file = openclaw_dir / "openclaw.json"
        config_file.write_text(json.dumps({
            "agents": {"list": []},
            "channels": {"telegram": {"enabled": True, "botToken": "123", "allowFrom": ["123456"]}}
        }))

        env_file = tmp_path / ".env"

        # Need to provide: GASTOWN_KIMI_KEYS, OPENCLAW_KIMI_KEY (TELEGRAM already in config)
        with patch("builtins.input", side_effect=["sk-gastown", "sk-openclaw"]):
            result = migrate_openclaw_launcher(
                openclaw_dir=openclaw_dir,
                env_file=env_file,
                interactive=True
            )

        assert result["success"] is True
        content = env_file.read_text()
        assert "OPENCLAW_KIMI_KEY=sk-openclaw" in content
        # TELEGRAM values come from config file, not prompts
        assert "TELEGRAM_BOT_TOKEN=123" in content
        assert "TELEGRAM_OWNER_ID=123456" in content
