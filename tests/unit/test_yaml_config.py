"""Tests for YAML configuration file support (issue #245)."""

from __future__ import annotations

from gasclaw.config import load_config, load_yaml_config


class TestYamlConfigLoading:
    """Tests for loading YAML config files."""

    def test_load_yaml_config_from_path(self, tmp_path, monkeypatch):
        """Load YAML config from a specific path."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
gastown:
  agent_count: 8
  rig_url: "git@github.com:org/repo.git"
""")
        cfg = load_yaml_config(str(config_file))
        assert cfg["gastown"]["agent_count"] == 8
        assert cfg["gastown"]["rig_url"] == "git@github.com:org/repo.git"

    def test_load_yaml_config_missing_file_returns_empty(self, tmp_path):
        """Missing YAML config returns empty dict."""
        cfg = load_yaml_config(str(tmp_path / "nonexistent.yaml"))
        assert cfg == {}

    def test_load_yaml_config_defaults_when_no_path(self, monkeypatch, tmp_path):
        """Default config path is GASCLAW_CONFIG or /workspace/config/gasclaw.yaml."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
maintenance:
  monitor_interval: 600
""")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))
        cfg = load_yaml_config()
        assert cfg["maintenance"]["monitor_interval"] == 600

    def test_load_yaml_invalid_yaml_logs_warning(self, tmp_path, caplog):
        """Invalid YAML logs a warning and returns empty dict."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("invalid: yaml: content: [")

        import logging
        with caplog.at_level(logging.WARNING):
            cfg = load_yaml_config(str(config_file))

        assert cfg == {}
        assert "Failed to parse YAML config" in caplog.text


class TestConfigMerge:
    """Tests for merging YAML config with env var config."""

    def test_yaml_overrides_defaults(self, monkeypatch, tmp_path):
        """YAML config values override env var defaults."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
gastown:
  agent_count: 10
  rig_url: "https://github.com/org/repo"
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.gt_agent_count == 10
        assert cfg.gt_rig_url == "https://github.com/org/repo"

    def test_env_vars_override_yaml(self, monkeypatch, tmp_path):
        """Environment variables override YAML config."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
gastown:
  agent_count: 10
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GT_AGENT_COUNT", "5")  # env var wins
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.gt_agent_count == 5  # env var takes precedence

    def test_yaml_partial_override(self, monkeypatch, tmp_path):
        """YAML can partially override - unset values use defaults."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
gastown:
  agent_count: 8
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.gt_agent_count == 8  # from YAML
        assert cfg.monitor_interval == 300  # default
        assert cfg.gt_rig_url == "/project"  # default

    def test_yaml_monitor_interval(self, monkeypatch, tmp_path):
        """YAML config can set monitor_interval."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
maintenance:
  monitor_interval: 600
  activity_deadline: 7200
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.monitor_interval == 600
        assert cfg.activity_deadline == 7200

    def test_yaml_dolt_port(self, monkeypatch, tmp_path):
        """YAML config can set dolt_port."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
services:
  dolt_port: 3308
  gateway_port: 18790
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.dolt_port == 3308
        assert cfg.gateway_port == 18790

    def test_yaml_project_dir(self, monkeypatch, tmp_path):
        """YAML config can set project_dir."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
paths:
  project_dir: "/workspace/gasclaw"
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.project_dir == "/workspace/gasclaw"


class TestYamlAgentIdentity:
    """Tests for agent identity in YAML config."""

    def test_yaml_agent_identity(self, monkeypatch, tmp_path):
        """YAML config can set agent identity."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
agent:
  id: "worker1"
  name: "Gasclaw Worker"
  emoji: "🤖"
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.agent_id == "worker1"
        assert cfg.agent_name == "Gasclaw Worker"
        assert cfg.agent_emoji == "🤖"


class TestYamlTelegramConfig:
    """Tests for Telegram configuration in YAML."""

    def test_yaml_telegram_allow_ids(self, monkeypatch, tmp_path):
        """YAML config can set telegram allowlists."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
telegram:
  allow_ids:
    - "111222333"
    - "444555666"
  group_ids:
    - "-100123456"
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert "111222333" in cfg.telegram_allow_ids
        assert "444555666" in cfg.telegram_allow_ids
        assert "-100123456" in cfg.telegram_group_ids


class TestEmptyYamlConfig:
    """Tests for empty or minimal YAML config."""

    def test_empty_yaml_uses_defaults(self, monkeypatch, tmp_path):
        """Empty YAML file results in defaults being used."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("")

        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        cfg = load_config()
        assert cfg.gt_agent_count == 6  # default
        assert cfg.monitor_interval == 300  # default

    def test_no_yaml_file_uses_defaults(self, monkeypatch, tmp_path):
        """Missing YAML file results in defaults being used."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(tmp_path / "nonexistent.yaml"))

        cfg = load_config()
        assert cfg.gt_agent_count == 6  # default


class TestYamlValidation:
    """Tests for YAML config validation."""

    def test_yaml_invalid_port_uses_default(self, monkeypatch, tmp_path, caplog):
        """Invalid port in YAML logs warning and uses default."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
services:
  dolt_port: 99999
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        import logging
        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.dolt_port == 3307  # default
        assert "dolt_port" in caplog.text.lower() or "DOLT_PORT" in caplog.text

    def test_yaml_negative_value_uses_default(self, monkeypatch, tmp_path, caplog):
        """Negative value in YAML logs warning and uses default."""
        config_file = tmp_path / "gasclaw.yaml"
        config_file.write_text("""
maintenance:
  monitor_interval: -100
""")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GASCLAW_CONFIG", str(config_file))

        import logging
        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.monitor_interval == 300  # default
