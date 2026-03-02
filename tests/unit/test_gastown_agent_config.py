"""Tests for gasclaw.gastown.agent_config."""

from __future__ import annotations

import json

from gasclaw.gastown.agent_config import write_agent_config


class TestWriteAgentConfig:
    def test_creates_config_file(self, tmp_path):
        write_agent_config(tmp_path)
        cfg_file = tmp_path / "settings" / "config.json"
        assert cfg_file.exists()

    def test_config_format(self, tmp_path):
        write_agent_config(tmp_path)
        cfg = json.loads((tmp_path / "settings" / "config.json").read_text())
        assert cfg["type"] == "town-settings"
        assert cfg["version"] == 1
        assert cfg["default_agent"] == "kimi-claude"

    def test_agent_definition(self, tmp_path):
        write_agent_config(tmp_path)
        cfg = json.loads((tmp_path / "settings" / "config.json").read_text())
        agent = cfg["agents"]["kimi-claude"]
        assert agent["command"] == "kimigas"
        assert agent["args"] == ["run", "claude", "--yolo"]

    def test_creates_settings_dir(self, tmp_path):
        write_agent_config(tmp_path)
        assert (tmp_path / "settings").is_dir()

    def test_idempotent(self, tmp_path):
        write_agent_config(tmp_path)
        write_agent_config(tmp_path)
        cfg = json.loads((tmp_path / "settings" / "config.json").read_text())
        assert cfg["default_agent"] == "kimi-claude"

    def test_returns_config_path(self, tmp_path):
        """Function returns the path to the written config file."""
        result = write_agent_config(tmp_path)
        assert result == tmp_path / "settings" / "config.json"
        assert result.exists()

    def test_overwrites_existing_config(self, tmp_path):
        """Overwrites existing config file with fresh content."""
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir()
        config_file = settings_dir / "config.json"
        config_file.write_text('{"old": "content"}')

        write_agent_config(tmp_path)

        cfg = json.loads(config_file.read_text())
        assert cfg["type"] == "town-settings"
        assert "old" not in cfg

    def test_creates_nested_directories(self, tmp_path):
        """Creates nested directories if needed."""
        deep_path = tmp_path / "a" / "b" / "c" / "gt"
        write_agent_config(deep_path)
        assert (deep_path / "settings" / "config.json").exists()
