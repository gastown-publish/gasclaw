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
