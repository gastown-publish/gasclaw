"""Tests for gasclaw.config."""

from __future__ import annotations

import logging

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
        for k, v in env_vars(GASTOWN_KIMI_KEYS="sk-a:sk-b:sk-c").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-a", "sk-b", "sk-c"]

    def test_single_key(self, monkeypatch, env_vars):
        """Single key (no colons) becomes a list of one."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="sk-only-one").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-only-one"]

    def test_empty_keys_filtered(self, monkeypatch, env_vars):
        """Empty segments from colons are filtered out."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="sk-a::sk-b:").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-a", "sk-b"]

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
        assert cfg.dolt_port == 3307

    def test_custom_optional_values(self, monkeypatch, env_vars):
        """Optional fields can be overridden."""
        for k, v in env_vars(
            GT_RIG_URL="git@github.com:org/repo.git",
            PROJECT_DIR="/workspace/repo",
            GT_AGENT_COUNT="8",
            MONITOR_INTERVAL="120",
            ACTIVITY_DEADLINE="1800",
            DOLT_PORT="3308",
        ).items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_rig_url == "git@github.com:org/repo.git"
        assert cfg.project_dir == "/workspace/repo"
        assert cfg.gt_agent_count == 8
        assert cfg.monitor_interval == 120
        assert cfg.activity_deadline == 1800
        assert cfg.dolt_port == 3308

    def test_keys_not_shared_by_default(self, monkeypatch, env_vars):
        """Gastown and OpenClaw keys are separate pools."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.openclaw_kimi_key not in cfg.gastown_kimi_keys

    @pytest.mark.parametrize("whitespace", ["", " ", "  ", "\t", "\n", " \t\n "])
    def test_whitespace_only_env_vars_treated_as_missing(self, monkeypatch, env_vars, whitespace):
        """Whitespace-only env vars should be treated as missing (spaces, tabs, newlines)."""
        for k, v in env_vars().items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", whitespace)
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

    def test_dolt_port_zero_defaults(self, monkeypatch, env_vars):
        """Zero dolt_port defaults to 3307."""
        for k, v in env_vars(DOLT_PORT="0").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.dolt_port == 3307

    def test_dolt_port_negative_defaults(self, monkeypatch, env_vars):
        """Negative dolt_port defaults to 3307."""
        for k, v in env_vars(DOLT_PORT="-1").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.dolt_port == 3307


class TestGasclawConfig:
    def test_dataclass_fields(self):
        """GasclawConfig has all expected fields."""
        cfg = GasclawConfig(
            gastown_kimi_keys=["sk-k1"],
            openclaw_kimi_key="sk-k2",
            telegram_bot_token="123:token",
            telegram_owner_id="123",
        )
        assert cfg.gt_rig_url == "/project"
        assert cfg.gt_agent_count == 6


class TestConfigValidation:
    """Tests for config validation in __post_init__."""

    def test_telegram_owner_id_must_be_numeric(self, monkeypatch):
        """TELEGRAM_OWNER_ID must be a numeric string."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "not_numeric")

        with pytest.raises(ValueError, match="TELEGRAM_OWNER_ID must be numeric"):
            load_config()

    def test_telegram_owner_id_numeric_is_valid(self, monkeypatch):
        """Numeric TELEGRAM_OWNER_ID is accepted."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        config = load_config()
        assert config.telegram_owner_id == "123456789"

    def test_project_dir_relative_path_warning(self, monkeypatch, caplog):
        """Relative PROJECT_DIR generates warning."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("PROJECT_DIR", "relative/path")

        with caplog.at_level(logging.WARNING):
            load_config()

        assert "should be an absolute path" in caplog.text

    def test_gt_rig_url_invalid_warning(self, monkeypatch, caplog):
        """Invalid GT_RIG_URL generates warning."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:token")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")
        monkeypatch.setenv("GT_RIG_URL", "invalid::url")

        with caplog.at_level(logging.WARNING):
            load_config()

        assert "should be a path or URL" in caplog.text


class TestParsePositiveIntWarnings:
    """Tests that _parse_positive_int logs warnings for invalid values."""

    def test_invalid_value_logs_warning(self, monkeypatch, env_vars, caplog):
        """Invalid integer value logs a warning."""

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

        for k, v in env_vars(MONITOR_INTERVAL="0").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.monitor_interval == 300  # Default used
        assert "MONITOR_INTERVAL" in caplog.text
        assert "must be positive" in caplog.text.lower()

    def test_negative_value_logs_warning(self, monkeypatch, env_vars, caplog):
        """Negative value logs a warning about positive requirement."""

        for k, v in env_vars(ACTIVITY_DEADLINE="-100").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.activity_deadline == 3600  # Default used
        assert "ACTIVITY_DEADLINE" in caplog.text
        assert "must be positive" in caplog.text.lower()

    def test_valid_value_no_warning(self, monkeypatch, env_vars, caplog):
        """Valid value does not log a warning."""

        for k, v in env_vars(GT_AGENT_COUNT="8").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.gt_agent_count == 8
        # Should not have any warnings about GT_AGENT_COUNT
        assert "GT_AGENT_COUNT" not in caplog.text


class TestInternalFunctions:
    """Direct tests for internal utility functions."""

    def test_require_env_returns_value(self, monkeypatch):
        """_require_env returns the env value when set (line 49-51)."""
        from gasclaw.config import _require_env

        monkeypatch.setenv("TEST_VAR", "test_value")
        result = _require_env("TEST_VAR")
        assert result == "test_value"

    def test_require_env_strips_whitespace(self, monkeypatch):
        """_require_env strips whitespace from value (line 48)."""
        from gasclaw.config import _require_env

        monkeypatch.setenv("TEST_VAR", "  value_with_spaces  ")
        result = _require_env("TEST_VAR")
        assert result == "value_with_spaces"

    def test_require_env_raises_on_missing(self, monkeypatch):
        """_require_env raises ValueError when env var missing (line 50-51)."""
        from gasclaw.config import _require_env

        monkeypatch.delenv("TEST_VAR_MISSING", raising=False)
        with pytest.raises(ValueError, match="Required environment variable TEST_VAR_MISSING"):
            _require_env("TEST_VAR_MISSING")

    def test_require_env_raises_on_empty(self, monkeypatch):
        """_require_env raises ValueError when env var is empty (line 49-51)."""
        from gasclaw.config import _require_env

        monkeypatch.setenv("TEST_VAR_EMPTY", "")
        with pytest.raises(ValueError, match="Required environment variable TEST_VAR_EMPTY"):
            _require_env("TEST_VAR_EMPTY")

    def test_require_env_raises_on_whitespace_only(self, monkeypatch):
        """_require_env raises ValueError when env var is whitespace only (line 48-51)."""
        from gasclaw.config import _require_env

        monkeypatch.setenv("TEST_VAR_WS", "   ")
        with pytest.raises(ValueError, match="Required environment variable TEST_VAR_WS"):
            _require_env("TEST_VAR_WS")

    def test_parse_keys_basic(self):
        """_parse_keys splits colon-separated values (line 55-56)."""
        from gasclaw.config import _parse_keys

        result = _parse_keys("key1:key2:key3")
        assert result == ["key1", "key2", "key3"]

    def test_parse_keys_filters_empty(self):
        """_parse_keys filters empty segments (line 56)."""
        from gasclaw.config import _parse_keys

        result = _parse_keys("key1::key2:")
        assert result == ["key1", "key2"]

    def test_parse_keys_strips_whitespace(self):
        """_parse_keys strips whitespace from keys (line 56)."""
        from gasclaw.config import _parse_keys

        result = _parse_keys("  key1  :  key2  ")
        assert result == ["key1", "key2"]


class TestConfigEdgeCases:
    """Additional edge case tests for config parsing."""

    def test_float_value_defaults_to_int(self, monkeypatch, env_vars, caplog):
        """Float value for integer config uses default."""

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

        for k, v in env_vars(GT_AGENT_COUNT="  42  ").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        # int() handles whitespace, so this should parse correctly
        assert cfg.gt_agent_count == 42
        assert "GT_AGENT_COUNT" not in caplog.text

    def test_scientific_notation_defaults(self, monkeypatch, env_vars, caplog):
        """Scientific notation for integer config uses default."""

        for k, v in env_vars(MONITOR_INTERVAL="1e3").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        # int("1e3") raises ValueError
        assert cfg.monitor_interval == 300  # Default used
        assert "MONITOR_INTERVAL" in caplog.text

    def test_hexadecimal_notation_defaults(self, monkeypatch, env_vars, caplog):
        """Hexadecimal notation for integer config uses default."""

        for k, v in env_vars(ACTIVITY_DEADLINE="0x100").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        # int("0x100") with base 10 raises ValueError
        assert cfg.activity_deadline == 3600  # Default used
        assert "ACTIVITY_DEADLINE" in caplog.text

    def test_octal_notation_parsed_as_decimal(self, monkeypatch, env_vars):
        """Octal notation is parsed as decimal - Issue #64.

        This is the documented behavior: only decimal integers are supported.
        Users expecting Unix octal behavior will get decimal interpretation.
        """
        for k, v in env_vars(GT_AGENT_COUNT="0777").items():
            monkeypatch.setenv(k, v)

        cfg = load_config()
        # int("0777") returns 777, not 511 (which would be octal 0o777)
        assert cfg.gt_agent_count == 777

    def test_octal_prefix_parsed_as_decimal(self, monkeypatch, env_vars, caplog):
        """Explicit octal prefix (0o) is parsed as decimal, not octal."""

        for k, v in env_vars(MONITOR_INTERVAL="0o755").items():
            monkeypatch.setenv(k, v)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        # int("0o755") with base 10 raises ValueError
        assert cfg.monitor_interval == 300  # Default used
        assert "MONITOR_INTERVAL" in caplog.text


class TestParsePositiveIntEdgeCases:
    """Tests for _parse_positive_int function edge cases."""

    def test_no_name_no_warning_on_invalid(self, monkeypatch, env_vars, caplog):
        """When name is empty, no warning is logged for invalid values."""

        from gasclaw.config import _parse_positive_int

        with caplog.at_level(logging.WARNING):
            result = _parse_positive_int("abc", default=42, name="")

        assert result == 42
        # Should not log any warning since name is empty
        assert caplog.text == ""

    def test_no_name_no_warning_on_zero(self, monkeypatch, env_vars, caplog):
        """When name is empty, no warning is logged for zero/negative values."""

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

    def test_parse_port_non_integer_defaults(self, monkeypatch, caplog):
        """Non-integer string for DOLT_PORT triggers exception handler and uses default."""
        from gasclaw.config import _parse_port

        with caplog.at_level(logging.WARNING):
            result = _parse_port("not_a_number", default=3307, name="DOLT_PORT")

        assert result == 3307
        assert "DOLT_PORT" in caplog.text
        assert "not a valid integer" in caplog.text.lower()

    def test_parse_port_float_string_defaults(self, monkeypatch, caplog):
        """Float string for DOLT_PORT triggers exception handler and uses default."""
        from gasclaw.config import _parse_port

        with caplog.at_level(logging.WARNING):
            result = _parse_port("3.14", default=3307, name="DOLT_PORT")

        assert result == 3307
        assert "DOLT_PORT" in caplog.text
        assert "not a valid integer" in caplog.text.lower()

    def test_parse_port_out_of_range_high_with_name(self, caplog):
        """Port > 65535 with name logs warning and uses default."""
        from gasclaw.config import _parse_port

        with caplog.at_level(logging.WARNING):
            result = _parse_port("70000", default=3307, name="TEST_PORT")

        assert result == 3307
        assert "TEST_PORT" in caplog.text
        assert "must be between 1 and 65535" in caplog.text

    def test_parse_port_out_of_range_high_no_name(self, caplog):
        """Port > 65535 without name silently uses default."""
        from gasclaw.config import _parse_port

        with caplog.at_level(logging.WARNING):
            result = _parse_port("70000", default=3307, name="")

        assert result == 3307
        assert caplog.text == ""

    def test_parse_port_type_error_with_name(self, caplog):
        """TypeError in _parse_port with name logs warning and uses default."""
        from gasclaw.config import _parse_port

        with caplog.at_level(logging.WARNING):
            # Passing None will trigger TypeError in int()
            result = _parse_port(None, default=3307, name="TEST_PORT")

        assert result == 3307
        assert "TEST_PORT" in caplog.text
        assert "not a valid integer" in caplog.text

    def test_parse_port_type_error_no_name(self, caplog):
        """TypeError in _parse_port without name silently uses default."""
        from gasclaw.config import _parse_port

        with caplog.at_level(logging.WARNING):
            result = _parse_port(None, default=3307, name="")

        assert result == 3307
        assert caplog.text == ""

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
        for k, v in env_vars(GASTOWN_KIMI_KEYS="sk-key with spaces:sk-another key").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-key with spaces", "sk-another key"]

    def test_keys_with_leading_trailing_whitespace(self, monkeypatch, env_vars):
        """Keys have leading/trailing whitespace stripped."""
        for k, v in env_vars(GASTOWN_KIMI_KEYS="  sk-key1  :  sk-key2  ").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-key1", "sk-key2"]

    def test_empty_optional_strings_default(self, monkeypatch, env_vars):
        """Empty optional string values use defaults."""
        for k, v in env_vars(GT_RIG_URL="", PROJECT_DIR="").items():
            monkeypatch.setenv(k, v)
        cfg = load_config()
        assert cfg.gt_rig_url == "/project"
        assert cfg.project_dir == "/project"


class TestConfigValidationNew:
    """Tests for new config validations (key format, port range, token format)."""

    def test_gastown_key_missing_sk_prefix_raises(self, monkeypatch):
        """GASTOWN_KIMI_KEYS without 'sk-' prefix raises ValueError."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "invalid-key")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-openclaw")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        with pytest.raises(ValueError, match="must start with 'sk-'"):
            load_config()

    def test_openclaw_key_missing_sk_prefix_raises(self, monkeypatch):
        """OPENCLAW_KIMI_KEY without 'sk-' prefix raises ValueError."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "invalid-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        with pytest.raises(ValueError, match="must start with 'sk-'"):
            load_config()

    @pytest.mark.parametrize("invalid_port,expected_default", [
        ("0", 3307),
        ("65536", 3307),
        ("100000", 3307),
        ("-1", 3307),
    ])
    def test_dolt_port_out_of_range_defaults(
        self, monkeypatch, caplog, invalid_port, expected_default
    ):
        """DOLT_PORT outside 1-65535 range logs warning and uses default."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("DOLT_PORT", invalid_port)

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.dolt_port == expected_default
        assert "DOLT_PORT" in caplog.text
        assert "must be between 1 and 65535" in caplog.text

    def test_telegram_bot_token_invalid_format_raises(self, monkeypatch):
        """TELEGRAM_BOT_TOKEN not in digits:alphanumeric format raises ValueError."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "invalid_token_format")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        with pytest.raises(ValueError, match="digits:alphanumeric"):
            load_config()

    def test_telegram_bot_token_missing_colon_raises(self, monkeypatch):
        """TELEGRAM_BOT_TOKEN without colon raises ValueError."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        with pytest.raises(ValueError, match="digits:alphanumeric"):
            load_config()

    def test_valid_config_passes_all_validations(self, monkeypatch):
        """Valid config with all correct formats loads successfully."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1:sk-key2")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-openclaw-key")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjklMNOpqrSTUvwxyz")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "987654321")
        monkeypatch.setenv("DOLT_PORT", "3308")

        cfg = load_config()
        assert cfg.gastown_kimi_keys == ["sk-key1", "sk-key2"]
        assert cfg.openclaw_kimi_key == "sk-openclaw-key"
        assert cfg.telegram_bot_token == "123456789:ABCdefGHIjklMNOpqrSTUvwxyz"
        assert cfg.telegram_owner_id == "987654321"
        assert cfg.dolt_port == 3308

    def test_key_validation_shows_prefix_only_in_error(self, monkeypatch):
        """Error message truncates key to first 10 chars for security."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "invalid-very-long-key-value")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-openclaw")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        with pytest.raises(ValueError) as exc_info:
            load_config()

        # Should only show first 10 chars of the key
        error_msg = str(exc_info.value)
        assert "invalid-ve" in error_msg
        assert "..." in error_msg
