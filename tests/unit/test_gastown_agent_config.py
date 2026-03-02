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
