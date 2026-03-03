"""Tests for gasclaw.openclaw.installer."""

from __future__ import annotations

import json

from gasclaw.openclaw.installer import write_openclaw_config


class TestWriteOpenclawConfig:
    def test_creates_config_file(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        assert (tmp_path / "openclaw.json").exists()

    def test_llm_config(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        model = cfg["agents"]["defaults"]["model"]
        assert "kimi" in model["primary"].lower() or "moonshot" in model["primary"].lower()

    def test_telegram_channel(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        # Check that telegram config has bot token and owner
        cfg_str = json.dumps(cfg)
        assert "123:ABC" in cfg_str
        assert "999" in cfg_str

    def test_gateway_port(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
            gateway_port=18789,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["gateway"]["port"] == 18789

    def test_auth_token_generated(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        token = cfg["gateway"]["auth"]["token"]
        assert len(token) == 64  # hex sha256

    def test_idempotent(self, tmp_path):
        for _ in range(2):
            write_openclaw_config(
                openclaw_dir=tmp_path,
                kimi_key="sk-test",
                bot_token="123:ABC",
                owner_id="999",
            )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["gateway"]["port"] == 18789

    def test_kimi_key_in_models(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-my-key",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        models = cfg["agents"]["defaults"].get("models", {})
        # At least one model entry should reference kimi
        assert any("kimi" in k.lower() or "moonshot" in k.lower() for k in models)

    def test_returns_config_path(self, tmp_path):
        """Function returns the path to the written config file."""
        result = write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        assert result == tmp_path / "openclaw.json"
        assert result.exists()

    def test_custom_gateway_port(self, tmp_path):
        """Custom gateway port is used correctly."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
            gateway_port=9999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["gateway"]["port"] == 9999

    def test_auth_token_preserved_on_restart(self, tmp_path):
        """Auth token is preserved when config file already exists."""
        # First call creates config with a token
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg1 = json.loads((tmp_path / "openclaw.json").read_text())
        token1 = cfg1["gateway"]["auth"]["token"]

        # Second call should preserve the same token
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg2 = json.loads((tmp_path / "openclaw.json").read_text())
        token2 = cfg2["gateway"]["auth"]["token"]

        assert token1 == token2  # Token preserved
        assert len(token1) == 64
        assert len(token2) == 64

    def test_auth_token_new_when_no_config(self, tmp_path):
        """New token generated when no config exists."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        token = cfg["gateway"]["auth"]["token"]
        assert len(token) == 64  # Valid hex token

    def test_creates_nested_directory(self, tmp_path):
        """Creates nested directories if needed."""
        deep_path = tmp_path / "a" / "b" / "c" / ".openclaw"
        write_openclaw_config(
            openclaw_dir=deep_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        assert (deep_path / "openclaw.json").exists()

    def test_kimi_key_in_env(self, tmp_path):
        """Kimi key is stored in env section."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-secret-key",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["env"]["MOONSHOT_API_KEY"] == "sk-secret-key"

    def test_owner_id_in_allowlist(self, tmp_path):
        """Owner ID is in the allowlist."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="555666777",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert "555666777" in cfg["channels"]["telegram"]["allowFrom"]

    def test_owner_id_as_integer(self, tmp_path):
        """Owner ID should be stored as integer for Telegram API compatibility."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999888777,  # Integer type
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        allow_from = cfg["channels"]["telegram"]["allowFrom"]
        assert "999888777" in allow_from
        assert isinstance(allow_from[0], str)

    def test_new_token_when_config_corrupted(self, tmp_path):
        """New token generated when existing config is corrupted."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text("not valid json!")
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads(config_path.read_text())
        token = cfg["gateway"]["auth"]["token"]
        assert len(token) == 64  # New valid token generated

    def test_memory_plugin_disabled(self, tmp_path):
        """File-based memory plugin is disabled in favor of beads."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["plugins"]["slots"]["memory"] == "none"

    def test_bd_root_in_env(self, tmp_path):
        """BD_ROOT env var is set for bead integration."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
            gt_root="/workspace/gt",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["env"]["BD_ROOT"] == "/workspace/gt"

    def test_agent_instructions_mention_beads(self, tmp_path):
        """Agent instructions tell OpenClaw to use beads, not files."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        agent = cfg["agents"]["list"][0]
        assert "bd" in agent["instructions"].lower() or "bead" in agent["instructions"].lower()

    def test_multiple_allow_ids(self, tmp_path):
        """Multiple allow IDs are included in allowlist."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
            allow_ids=["111", "222"],
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        allow_from = cfg["channels"]["telegram"]["allowFrom"]
        assert "999" in allow_from
        assert "111" in allow_from
        assert "222" in allow_from

    def test_group_ids_add_group_allow_from(self, tmp_path):
        """Group IDs add groupAllowFrom and groupPolicy."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
            group_ids=["-5054397264", "-123456789"],
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        telegram = cfg["channels"]["telegram"]
        assert "groupAllowFrom" in telegram
        assert "-5054397264" in telegram["groupAllowFrom"]
        assert "-123456789" in telegram["groupAllowFrom"]
        assert telegram["groupPolicy"] == "allowlist"

    def test_custom_agent_identity(self, tmp_path):
        """Custom agent identity is written to config."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
            agent_id="openclawmaster",
            agent_name="OpenClawMaster",
            agent_emoji="🦾",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        agent = cfg["agents"]["list"][0]
        assert agent["id"] == "openclawmaster"
        assert agent["identity"]["name"] == "OpenClawMaster"
        assert agent["identity"]["emoji"] == "🦾"

    def test_no_duplicate_owner_in_allowlist(self, tmp_path):
        """Owner ID is not duplicated when also in allow_ids."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
            allow_ids=["999", "111"],  # 999 is owner
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        allow_from = cfg["channels"]["telegram"]["allowFrom"]
        # 999 should appear only once
        assert allow_from.count("999") == 1
        assert "111" in allow_from

    def test_no_group_config_when_no_group_ids(self, tmp_path):
        """Group fields are not present when no group_ids provided."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        telegram = cfg["channels"]["telegram"]
        assert "groupAllowFrom" not in telegram
        assert "groupPolicy" not in telegram
