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

    def test_new_token_when_config_corrupted(self, tmp_path):
        """New token generated when existing config is corrupted."""
        config_path = tmp_path / "openclaw.json"
        config_path.write_text("not valid json!")

        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id="999",
        )
        cfg = json.loads(config_path.read_text())
        token = cfg["gateway"]["auth"]["token"]
        assert len(token) == 64  # New valid token generated
