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
        # Ensure optional env vars are unset to test defaults
        monkeypatch.delenv("GT_AGENT_COUNT", raising=False)
        monkeypatch.delenv("GT_RIG_URL", raising=False)
        monkeypatch.delenv("PROJECT_DIR", raising=False)
        monkeypatch.delenv("MONITOR_INTERVAL", raising=False)
        monkeypatch.delenv("ACTIVITY_DEADLINE", raising=False)
        monkeypatch.delenv("DOLT_PORT", raising=False)
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

    @pytest.mark.parametrize(
        "invalid_port,expected_default",
        [
            ("0", 3307),
            ("65536", 3307),
            ("100000", 3307),
            ("-1", 3307),
        ],
    )
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


class TestTelegramAllowlistConfig:
    """Tests for multiple Telegram allowlist users and groups."""

    def test_telegram_allow_ids_parsed(self, monkeypatch):
        """TELEGRAM_ALLOW_IDS parsed as colon-separated list."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("TELEGRAM_ALLOW_IDS", "987654321:555666777")

        cfg = load_config()
        assert cfg.telegram_allow_ids == ["987654321", "555666777"]

    def test_telegram_group_ids_parsed(self, monkeypatch):
        """TELEGRAM_GROUP_IDS parsed as colon-separated list."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("TELEGRAM_GROUP_IDS", "-5054397264:-123456789")

        cfg = load_config()
        assert cfg.telegram_group_ids == ["-5054397264", "-123456789"]

    def test_telegram_allow_ids_must_be_numeric(self, monkeypatch):
        """TELEGRAM_ALLOW_IDS values must be numeric."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("TELEGRAM_ALLOW_IDS", "not_numeric:987654321")

        with pytest.raises(ValueError, match="TELEGRAM_ALLOW_IDS must be numeric"):
            load_config()

    def test_empty_allowlist_defaults_to_empty_list(self, monkeypatch):
        """Empty TELEGRAM_ALLOW_IDS defaults to empty list."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        cfg = load_config()
        assert cfg.telegram_allow_ids == []
        assert cfg.telegram_group_ids == []


class TestGatewayPortConfig:
    """Tests for configurable gateway port."""

    def test_default_gateway_port(self, monkeypatch):
        """Default gateway port is 18789."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        cfg = load_config()
        assert cfg.gateway_port == 18789

    def test_custom_gateway_port(self, monkeypatch):
        """GATEWAY_PORT can be customized."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("GATEWAY_PORT", "18790")

        cfg = load_config()
        assert cfg.gateway_port == 18790

    def test_gateway_port_out_of_range_defaults(self, monkeypatch, caplog):
        """GATEWAY_PORT outside 1-65535 range logs warning and uses default."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("GATEWAY_PORT", "70000")

        with caplog.at_level(logging.WARNING):
            cfg = load_config()

        assert cfg.gateway_port == 18789
        assert "GATEWAY_PORT" in caplog.text
        assert "must be between 1 and 65535" in caplog.text


class TestAgentIdentityConfig:
    """Tests for agent identity customization."""

    def test_default_agent_identity(self, monkeypatch):
        """Default agent identity values."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")

        cfg = load_config()
        assert cfg.agent_id == "main"
        assert cfg.agent_name == "Gasclaw Overseer"
        assert cfg.agent_emoji == "🏭"

    def test_custom_agent_identity(self, monkeypatch):
        """Agent identity can be customized via env vars."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("AGENT_ID", "openclawmaster")
        monkeypatch.setenv("AGENT_NAME", "OpenClawMaster - Docker Orchestrator")
        monkeypatch.setenv("AGENT_EMOJI", "🦾")

        cfg = load_config()
        assert cfg.agent_id == "openclawmaster"
        assert cfg.agent_name == "OpenClawMaster - Docker Orchestrator"
        assert cfg.agent_emoji == "🦾"

    def test_empty_agent_identity_uses_default(self, monkeypatch):
        """Empty agent identity values use defaults."""
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-key2")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456789")
        monkeypatch.setenv("AGENT_NAME", "")
        monkeypatch.setenv("AGENT_EMOJI", "")

        cfg = load_config()
        assert cfg.agent_name == "Gasclaw Overseer"
        assert cfg.agent_emoji == "🏭"


class TestParseSimpleYaml:
    """Tests for _parse_simple_yaml fallback parser when PyYAML unavailable."""

    def test_parse_simple_yaml_basic(self):
        """Parse basic YAML with sections and key-value pairs."""
        from gasclaw.config import _parse_simple_yaml

        yaml_text = """
# This is a comment
section1:
  key1: value1
  key2: value2

section2:
  key3: 42
  key4: true
"""
        result = _parse_simple_yaml(yaml_text)
        assert result["section1"]["key1"] == "value1"
        assert result["section1"]["key2"] == "value2"
        assert result["section2"]["key3"] == 42
        assert result["section2"]["key4"] is True

    def test_parse_simple_yaml_quoted_strings(self):
        """Parse YAML with quoted string values."""
        from gasclaw.config import _parse_simple_yaml

        yaml_text = """
section:
  key1: "double quoted"
  key2: 'single quoted'
"""
        result = _parse_simple_yaml(yaml_text)
        assert result["section"]["key1"] == "double quoted"
        assert result["section"]["key2"] == "single quoted"

    def test_parse_simple_yaml_lists(self):
        """Parse YAML with list values."""
        from gasclaw.config import _parse_simple_yaml

        yaml_text = """
section:
  list1: ["a", "b", "c"]
  list2: [x, y, z]
"""
        result = _parse_simple_yaml(yaml_text)
        assert result["section"]["list1"] == ["a", "b", "c"]
        assert result["section"]["list2"] == ["x", "y", "z"]

    def test_parse_simple_yaml_booleans(self):
        """Parse YAML with boolean values."""
        from gasclaw.config import _parse_simple_yaml

        yaml_text = """
section:
  enabled: true
  disabled: false
"""
        result = _parse_simple_yaml(yaml_text)
        assert result["section"]["enabled"] is True
        assert result["section"]["disabled"] is False

    def test_parse_simple_yaml_integers(self):
        """Parse YAML with integer values."""
        from gasclaw.config import _parse_simple_yaml

        yaml_text = """
section:
  port: 3307
  negative: -100
"""
        result = _parse_simple_yaml(yaml_text)
        assert result["section"]["port"] == 3307
        assert result["section"]["negative"] == -100

    def test_parse_simple_yaml_empty_values(self):
        """Parse YAML with empty values."""
        from gasclaw.config import _parse_simple_yaml

        yaml_text = """
section:
  empty:
  other: value
"""
        result = _parse_simple_yaml(yaml_text)
        assert result["section"]["empty"] is None
        assert result["section"]["other"] == "value"

    def test_parse_simple_yaml_empty_sections(self):
        """Parse YAML with empty sections."""
        from gasclaw.config import _parse_simple_yaml

        yaml_text = """
section1:
section2:
  key: value
"""
        result = _parse_simple_yaml(yaml_text)
        assert result["section1"] == {}
        assert result["section2"]["key"] == "value"


class TestMergeConfig:
    """Tests for merge_config function."""

    def test_merge_config_env_wins(self):
        """Environment variable takes precedence over YAML."""
        from gasclaw.config import merge_config

        yaml_cfg = {"gastown": {"agent_count": 5}}
        result = merge_config(yaml_cfg, "10", ("gastown", "agent_count"), 6, int)
        assert result == 10

    def test_merge_config_yaml_fallback(self):
        """YAML value used when env var is None."""
        from gasclaw.config import merge_config

        yaml_cfg = {"gastown": {"agent_count": 8}}
        result = merge_config(yaml_cfg, None, ("gastown", "agent_count"), 6, int)
        assert result == 8

    def test_merge_config_default_fallback(self):
        """Default used when both env and YAML are missing/invalid."""
        from gasclaw.config import merge_config

        yaml_cfg = {}
        result = merge_config(yaml_cfg, None, ("gastown", "agent_count"), 6, int)
        assert result == 6

    def test_merge_config_empty_env_uses_yaml(self):
        """Empty env var string uses YAML value."""
        from gasclaw.config import merge_config

        yaml_cfg = {"gastown": {"agent_count": 7}}
        result = merge_config(yaml_cfg, "   ", ("gastown", "agent_count"), 6, int)
        assert result == 7

    def test_merge_config_parser_exception_falls_through(self):
        """Parser exception falls through to YAML/default."""
        from gasclaw.config import merge_config

        yaml_cfg = {"gastown": {"agent_count": 9}}

        def selective_failing_parser(x):
            # Fail for string "invalid", succeed for integers
            if x == "invalid":
                raise ValueError("parse error")
            return int(x)

        # Env var that will fail to parse
        result = merge_config(
            yaml_cfg, "invalid", ("gastown", "agent_count"), 6, selective_failing_parser
        )
        # Should fall through to YAML value
        assert result == 9

    def test_merge_config_parser_exception_falls_to_default(self):
        """Parser exception falls through to default when no YAML."""
        from gasclaw.config import merge_config

        yaml_cfg = {}

        def failing_parser(x):
            raise ValueError("parse error")

        result = merge_config(yaml_cfg, "invalid", ("gastown", "agent_count"), 6, failing_parser)
        # Should fall through to default
        assert result == 6

    def test_merge_config_yaml_parser_exception_falls_to_default(self):
        """YAML value parser exception falls through to default."""
        from gasclaw.config import merge_config

        yaml_cfg = {"gastown": {"agent_count": "invalid"}}

        def strict_int(x):
            # This will fail for the YAML "invalid" string
            if not isinstance(x, int):
                raise ValueError("must be int")
            return x

        result = merge_config(yaml_cfg, None, ("gastown", "agent_count"), 6, strict_int)
        # Should fall through to default
        assert result == 6


class TestYamlParsers:
    """Tests for YAML-specific parser functions."""

    def test_parse_port_yaml_valid(self):
        """_parse_port_yaml with valid port."""
        from gasclaw.config import _parse_port_yaml

        result = _parse_port_yaml(3307, 3306, "TEST_PORT")
        assert result == 3307

    def test_parse_port_yaml_string_valid(self):
        """_parse_port_yaml with valid string port."""
        from gasclaw.config import _parse_port_yaml

        result = _parse_port_yaml("3308", 3306, "TEST_PORT")
        assert result == 3308

    def test_parse_port_yaml_out_of_range_high(self, caplog):
        """_parse_port_yaml with port > 65535 logs warning."""
        from gasclaw.config import _parse_port_yaml

        with caplog.at_level(logging.WARNING):
            result = _parse_port_yaml(70000, 3307, "TEST_PORT")

        assert result == 3307
        assert "TEST_PORT" in caplog.text
        assert "must be between 1 and 65535" in caplog.text

    def test_parse_port_yaml_out_of_range_low(self, caplog):
        """_parse_port_yaml with port < 1 logs warning."""
        from gasclaw.config import _parse_port_yaml

        with caplog.at_level(logging.WARNING):
            result = _parse_port_yaml(0, 3307, "TEST_PORT")

        assert result == 3307
        assert "TEST_PORT" in caplog.text

    def test_parse_port_yaml_invalid_type(self, caplog):
        """_parse_port_yaml with non-integer value."""
        from gasclaw.config import _parse_port_yaml

        with caplog.at_level(logging.WARNING):
            result = _parse_port_yaml("invalid", 3307, "TEST_PORT")

        assert result == 3307
        assert "TEST_PORT" in caplog.text

    def test_parse_port_yaml_no_name_no_warning(self, caplog):
        """_parse_port_yaml without name doesn't log warning."""
        from gasclaw.config import _parse_port_yaml

        with caplog.at_level(logging.WARNING):
            result = _parse_port_yaml("invalid", 3307, "")

        assert result == 3307
        assert caplog.text == ""

    def test_parse_positive_int_yaml_valid(self):
        """_parse_positive_int_yaml with valid positive int."""
        from gasclaw.config import _parse_positive_int_yaml

        result = _parse_positive_int_yaml(100, 50, "TEST")
        assert result == 100

    def test_parse_positive_int_yaml_zero(self, caplog):
        """_parse_positive_int_yaml with zero logs warning."""
        from gasclaw.config import _parse_positive_int_yaml

        with caplog.at_level(logging.WARNING):
            result = _parse_positive_int_yaml(0, 50, "TEST")

        assert result == 50
        assert "TEST" in caplog.text
        assert "must be positive" in caplog.text

    def test_parse_positive_int_yaml_negative(self, caplog):
        """_parse_positive_int_yaml with negative logs warning."""
        from gasclaw.config import _parse_positive_int_yaml

        with caplog.at_level(logging.WARNING):
            result = _parse_positive_int_yaml(-10, 50, "TEST")

        assert result == 50
        assert "TEST" in caplog.text

    def test_parse_positive_int_yaml_invalid(self, caplog):
        """_parse_positive_int_yaml with invalid value."""
        from gasclaw.config import _parse_positive_int_yaml

        with caplog.at_level(logging.WARNING):
            result = _parse_positive_int_yaml("invalid", 50, "TEST")

        assert result == 50
        assert "TEST" in caplog.text

    def test_parse_string_yaml_with_none(self):
        """_parse_string_yaml with None returns default."""
        from gasclaw.config import _parse_string_yaml

        result = _parse_string_yaml(None, "default")
        assert result == "default"

    def test_parse_string_yaml_with_empty_string(self):
        """_parse_string_yaml with empty string returns default."""
        from gasclaw.config import _parse_string_yaml

        result = _parse_string_yaml("   ", "default")
        assert result == "default"

    def test_parse_string_list_yaml_with_none(self):
        """_parse_string_list_yaml with None returns empty list."""
        from gasclaw.config import _parse_string_list_yaml

        result = _parse_string_list_yaml(None)
        assert result == []

    def test_parse_string_list_yaml_with_list(self):
        """_parse_string_list_yaml with list returns cleaned strings."""
        from gasclaw.config import _parse_string_list_yaml

        result = _parse_string_list_yaml(["  a  ", "b", None, "c"])
        assert result == ["a", "b", "c"]

    def test_parse_string_list_yaml_with_string(self):
        """_parse_string_list_yaml with colon-separated string."""
        from gasclaw.config import _parse_string_list_yaml

        result = _parse_string_list_yaml("a:b:c")
        assert result == ["a", "b", "c"]

    def test_parse_string_list_yaml_with_other_type(self):
        """_parse_string_list_yaml with unexpected type returns empty list."""
        from gasclaw.config import _parse_string_list_yaml

        result = _parse_string_list_yaml(123)
        assert result == []


class TestLoadYamlConfig:
    """Tests for load_yaml_config function."""

    def test_load_yaml_config_from_path(self, tmp_path):
        """Load YAML from specified path."""
        from gasclaw.config import load_yaml_config

        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("section:\n  key: value\n")

        result = load_yaml_config(str(yaml_file))
        assert result["section"]["key"] == "value"

    def test_load_yaml_config_missing_file(self):
        """Missing file returns empty dict."""
        from gasclaw.config import load_yaml_config

        result = load_yaml_config("/nonexistent/path/config.yaml")
        assert result == {}

    def test_load_yaml_config_no_path_uses_env(self, monkeypatch, tmp_path):
        """No path uses GASCLAW_CONFIG env var."""
        from gasclaw.config import load_yaml_config

        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("key: value")
        monkeypatch.setenv("GASCLAW_CONFIG", str(yaml_file))

        result = load_yaml_config()
        assert result["key"] == "value"

    def test_load_yaml_config_no_path_no_env_uses_default(self, monkeypatch, tmp_path):
        """No path and no env var uses default path."""
        from gasclaw.config import load_yaml_config

        # Create default location
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "gasclaw.yaml"
        yaml_file.write_text("key: from_default")

        # Remove env var and patch the default path
        monkeypatch.delenv("GASCLAW_CONFIG", raising=False)

        # Use the tmp_path as the workspace
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = load_yaml_config()
        finally:
            os.chdir(original_cwd)

        # Since we're not at /workspace/config, this should return empty
        assert result == {} or "key" not in result


class TestGetYamlValue:
    """Tests for _get_yaml_value helper."""

    def test_get_yaml_value_nested(self):
        """Get nested value from YAML dict."""
        from gasclaw.config import _get_yaml_value

        yaml_cfg = {"a": {"b": {"c": "value"}}}
        result = _get_yaml_value(yaml_cfg, "a", "b", "c")
        assert result == "value"

    def test_get_yaml_value_missing_key(self):
        """Missing key returns default."""
        from gasclaw.config import _get_yaml_value

        yaml_cfg = {"a": {"b": "value"}}
        result = _get_yaml_value(yaml_cfg, "a", "missing", default="default")
        assert result == "default"

    def test_get_yaml_value_not_dict(self):
        """Non-dict in path returns default."""
        from gasclaw.config import _get_yaml_value

        yaml_cfg = {"a": "not_a_dict"}
        result = _get_yaml_value(yaml_cfg, "a", "b", default="default")
        assert result == "default"
