"""Tests for gasclaw.config."""

from __future__ import annotations

import pytest

from gasclaw.config import GasclawConfig, load_config


class TestLoadConfig:
    def test_valid_config(self, monkeypatch, env_vars):
        """All required env vars present — config loads correctly."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-kimi-key1", "sk-kimi-key2"]
        assert cfg.openclaw_kimi_key == "sk-kimi-openclaw"
        assert cfg.telegram_bot_token == "123456:ABC-DEF"
        assert cfg.telegram_owner_id == "987654321"

    def test_missing_gastown_keys(self, monkeypatch, env_vars):
        """Missing GASTOWN_KIMI_KEYS raises ValueError."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS")
        with pytest.raises(ValueError, match="GASTOWN_KIMI_KEYS"):
            load_config()

    def test_missing_openclaw_key(self, monkeypatch, env_vars):
        """Missing OPENCLAW_KIMI_KEY raises ValueError."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("OPENCLAW_KIMI_KEY")
        with pytest.raises(ValueError, match="OPENCLAW_KIMI_KEY"):
            load_config()

    def test_missing_telegram_token(self, monkeypatch, env_vars):
        """Missing TELEGRAM_BOT_TOKEN raises ValueError."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            load_config()

    def test_missing_telegram_owner(self, monkeypatch, env_vars):
        """Missing TELEGRAM_OWNER_ID raises ValueError."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        monkeypatch.delenv("TELEGRAM_OWNER_ID")
        with pytest.raises(ValueError, match="TELEGRAM_OWNER_ID"):
            load_config()

    def test_key_parsing_colon_separated(self, monkeypatch, env_vars):
        """Colon-separated keys are parsed into a list."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="a:b:c").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["a", "b", "c"]

    def test_single_key(self, monkeypatch, env_vars):
        """Single key (no colons) becomes a list of one."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="sk-only-one").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-only-one"]

    def test_empty_keys_filtered(self, monkeypatch, env_vars):
        """Empty segments from colons are filtered out."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="a::b:").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["a", "b"]

    def test_defaults(self, monkeypatch, env_vars):
        """Optional fields use defaults."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_rig_url == "/project"
        assert cfg.project_dir == "/project"
        assert cfg.gt_agent_count == 6
        assert cfg.monitor_interval == 300
        assert cfg.activity_deadline == 3600

    def test_custom_optional_values(self, monkeypatch, env_vars):
        """Optional fields can be overridden."""
        for k, v in env_vars(
            GT_RIG_URL="git@github.com:org/repo.git",
            PROJECT_DIR="/workspace/repo",
            GT_AGENT_COUNT="8",
            MONITOR_INTERVAL="120",
            ACTIVITY_DEADLINE="1800",
        ).items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_rig_url == "git@github.com:org/repo.git"
        assert cfg.project_dir == "/workspace/repo"
        assert cfg.gt_agent_count == 8
        assert cfg.monitor_interval == 120
        assert cfg.activity_deadline == 1800

    def test_keys_not_shared_by_default(self, monkeypatch, env_vars):
        """Gastown and OpenClaw keys are separate pools."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.openclaw_kimi_key not in cfg.gastown_kimi_keys


    def test_whitespace_only_env_vars_treated_as_missing(self, monkeypatch, env_vars):
        """Whitespace-only env vars should be treated as missing."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "   ")
        with pytest.raises(ValueError, match="GASTOWN_KIMI_KEYS"):
            load_config()

    def test_only_colons_in_keys_raises(self, monkeypatch, env_vars):
        """Keys containing only colons should raise ValueError."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", ":::")
        with pytest.raises(ValueError, match="GASTOWN_KIMI_KEYS"):
            load_config()

    def test_gt_agent_count_zero_defaults_to_six(self, monkeypatch, env_vars):
        """Zero gt_agent_count defaults to 6."""
        for k, v in env_vars(GT_AGENT_COUNT="0").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_agent_count == 6

    def test_gt_agent_count_negative_defaults_to_six(self, monkeypatch, env_vars):
        """Negative gt_agent_count defaults to 6."""
        for k, v in env_vars(GT_AGENT_COUNT="-1").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_agent_count == 6

    def test_monitor_interval_zero_defaults(self, monkeypatch, env_vars):
        """Zero monitor_interval defaults to 300."""
        for k, v in env_vars(MONITOR_INTERVAL="0").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.monitor_interval == 300

    def test_monitor_interval_negative_defaults(self, monkeypatch, env_vars):
        """Negative monitor_interval defaults to 300."""
        for k, v in env_vars(MONITOR_INTERVAL="-10").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.monitor_interval == 300

    def test_activity_deadline_zero_defaults(self, monkeypatch, env_vars):
        """Zero activity_deadline defaults to 3600."""
        for k, v in env_vars(ACTIVITY_DEADLINE="0").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.activity_deadline == 3600

    def test_activity_deadline_negative_defaults(self, monkeypatch, env_vars):
        """Negative activity_deadline defaults to 3600."""
        for k, v in env_vars(ACTIVITY_DEADLINE="-100").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.activity_deadline == 3600


class TestGasclawConfig:
    def test_dataclass_fields(self):
        """GasclawConfig has all expected fields."""
        cfg = GasclawConfig(
            gastown_kimi_keys=["k1"],
            openclaw_kimi_key="k2",
            telegram_bot_token="t",
            telegram_owner_id="123",
        )
        assert cfg.gt_rig_url == "/project"
        assert cfg.gt_agent_count == 6


class TestParsePositiveIntWarnings:
    """Tests that _parse_positive_int logs warnings for invalid values."""

    def test_invalid_value_logs_warning(self, monkeypatch, env_vars, caplog):
        """Invalid integer value logs a warning."""
        import logging
        for k, v in env_vars(GT_AGENT_COUNT="abc").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.gt_agent_count == 6  # Default used
        assert "GT_AGENT_COUNT" in caplog.text
        assert "abc" in caplog.text
        assert "not a valid integer" in caplog.text.lower()

    def test_zero_value_logs_warning(self, monkeypatch, env_vars, caplog):
        """Zero value logs a warning about positive requirement."""
        import logging
        for k, v in env_vars(MONITOR_INTERVAL="0").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.monitor_interval == 300  # Default used
        assert "MONITOR_INTERVAL" in caplog.text
        assert "must be positive" in caplog.text.lower()

    def test_negative_value_logs_warning(self, monkeypatch, env_vars, caplog):
        """Negative value logs a warning about positive requirement."""
        import logging
        for k, v in env_vars(ACTIVITY_DEADLINE="-100").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.activity_deadline == 3600  # Default used
        assert "ACTIVITY_DEADLINE" in caplog.text
        assert "must be positive" in caplog.text.lower()

    def test_valid_value_no_warning(self, monkeypatch, env_vars, caplog):
        """Valid value does not log a warning."""
        import logging
        for k, v in env_vars(GT_AGENT_COUNT="8").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.gt_agent_count == 8
        # Should not have any warnings about GT_AGENT_COUNT
        assert "GT_AGENT_COUNT" not in caplog.text


class TestConfigEdgeCases:
    """Additional edge case tests for config parsing."""

    def test_float_value_defaults_to_int(self, monkeypatch, env_vars, caplog):
        """Float value for integer config uses default."""
        import logging
        for k, v in env_vars(GT_AGENT_COUNT="3.14").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.gt_agent_count == 6  # Default used
        assert "GT_AGENT_COUNT" in caplog.text
        assert "not a valid integer" in caplog.text.lower()

    def test_leading_zeros_parsed_correctly(self, monkeypatch, env_vars):
        """Values with leading zeros are parsed as integers."""
        for k, v in env_vars(GT_AGENT_COUNT="007").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_agent_count == 7

    def test_plus_sign_prefix(self, monkeypatch, env_vars):
        """Positive numbers with + prefix are accepted."""
        for k, v in env_vars(GT_AGENT_COUNT="+10").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_agent_count == 10

    def test_whitespace_in_integer_value(self, monkeypatch, env_vars, caplog):
        """Whitespace around integer values is handled."""
        import logging
        for k, v in env_vars(GT_AGENT_COUNT="  42  ").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        # int() handles whitespace, so this should parse correctly
        assert cfg.gt_agent_count == 42
        assert "GT_AGENT_COUNT" not in caplog.text

    def test_scientific_notation_defaults(self, monkeypatch, env_vars, caplog):
        """Scientific notation for integer config uses default."""
        import logging
        for k, v in env_vars(MONITOR_INTERVAL="1e3").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        # int("1e3") raises ValueError
        assert cfg.monitor_interval == 300  # Default used
        assert "MONITOR_INTERVAL" in caplog.text

    def test_hexadecimal_notation_defaults(self, monkeypatch, env_vars, caplog):
        """Hexadecimal notation for integer config uses default."""
        import logging
        for k, v in env_vars(ACTIVITY_DEADLINE="0x100").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        # int("0x100") with base 10 raises ValueError
        assert cfg.activity_deadline == 3600  # Default used
        assert "ACTIVITY_DEADLINE" in caplog.text


class TestParsePositiveIntEdgeCases:
    """Tests for _parse_positive_int function edge cases."""

    def test_no_name_no_warning_on_invalid(self, monkeypatch, env_vars, caplog):
        """When name is empty, no warning is logged for invalid values."""
        import logging

        from gasclaw.config import _parse_positive_int

        with caplog.at_level(logging.WARNING):
            result = _parse_positive_int("abc", default=42, name="")

        assert result == 42
        # Should not log any warning since name is empty
        assert caplog.text == ""

    def test_no_name_no_warning_on_zero(self, monkeypatch, env_vars, caplog):
        """When name is empty, no warning is logged for zero/negative values."""
        import logging

        from gasclaw.config import _parse_positive_int

        with caplog.at_level(logging.WARNING):
            result = _parse_positive_int("0", default=100, name="")

        assert result == 100
        # Should not log any warning since name is empty
        assert caplog.text == ""

    def test_no_name_returns_default_on_error(self):
        """Default is returned when parsing fails and name is empty."""
        from gasclaw.config import _parse_positive_int

        result = _parse_positive_int("invalid", default=99, name="")
        assert result == 99

    def test_valid_value_with_name(self):
        """Valid value returns correctly even with name provided."""
        from gasclaw.config import _parse_positive_int

        result = _parse_positive_int("50", default=10, name="TEST_VAR")
        assert result == 50

    def test_large_integer_accepted(self, monkeypatch, env_vars):
        """Very large integers are accepted."""
        for k, v in env_vars(ACTIVITY_DEADLINE="999999").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.activity_deadline == 999999

    def test_keys_with_internal_whitespace(self, monkeypatch, env_vars):
        """Keys with internal whitespace have it preserved."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="key with spaces:another key").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["key with spaces", "another key"]

    def test_keys_with_leading_trailing_whitespace(self, monkeypatch, env_vars):
        """Keys have leading/trailing whitespace stripped."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="  key1  :  key2  ").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["key1", "key2"]

    def test_empty_optional_strings_default(self, monkeypatch, env_vars):
        """Empty optional string values use defaults."""
        for k, v in env_vars(GT_RIG_URL="", PROJECT_DIR="").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_rig_url == "/project"
        assert cfg.project_dir == "/project"
