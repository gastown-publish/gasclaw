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
            owner_id=999,
        )
        assert (tmp_path / "openclaw.json").exists()

    def test_llm_config(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        model = cfg["agents"]["defaults"]["model"]
        assert "kimi" in model["primary"].lower() or "moonshot" in model["primary"].lower()

    def test_telegram_allowlist_policy(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        tg = cfg["channels"]["telegram"]
        assert tg["botToken"] == "123:ABC"
        assert tg["dmPolicy"] == "allowlist"
        assert tg["allowFrom"] == ["999"]
        assert tg["groupPolicy"] == "allowlist"
        assert tg["groupAllowFrom"] == ["999"]

    def test_gateway_port(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
            gateway_port=18789,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["gateway"]["port"] == 18789

    def test_auth_token_generated(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        token = cfg["gateway"]["auth"]["token"]
        assert len(token) == 64

    def test_idempotent(self, tmp_path):
        for _ in range(2):
            write_openclaw_config(
                openclaw_dir=tmp_path,
                kimi_key="sk-test",
                bot_token="123:ABC",
                owner_id=999,
            )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["gateway"]["port"] == 18789

    def test_kimi_key_in_models(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-my-key",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        models = cfg["agents"]["defaults"].get("models", {})
        assert any("kimi" in k.lower() or "moonshot" in k.lower() for k in models)

    def test_returns_config_path(self, tmp_path):
        result = write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        assert result == tmp_path / "openclaw.json"
        assert result.exists()

    def test_custom_gateway_port(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
            gateway_port=9999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["gateway"]["port"] == 9999

    def test_auth_token_preserved_on_restart(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg1 = json.loads((tmp_path / "openclaw.json").read_text())
        token1 = cfg1["gateway"]["auth"]["token"]

        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg2 = json.loads((tmp_path / "openclaw.json").read_text())
        token2 = cfg2["gateway"]["auth"]["token"]

        assert token1 == token2
        assert len(token1) == 64

    def test_creates_nested_directory(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c" / ".openclaw"
        write_openclaw_config(
            openclaw_dir=deep_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        assert (deep_path / "openclaw.json").exists()

    def test_kimi_key_in_env(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-secret-key",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["env"]["MOONSHOT_API_KEY"] == "sk-secret-key"

    def test_ack_reaction(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["messages"]["ackReactionScope"] == "none"
        assert cfg["messages"]["ackReaction"] == ""

    def test_new_token_when_config_corrupted(self, tmp_path):
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
        assert len(token) == 64

    def test_memory_plugin_disabled(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["plugins"]["slots"]["memory"] == "none"

    def test_bd_root_in_env(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
            gt_root="/workspace/gt",
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["env"]["BD_ROOT"] == "/workspace/gt"

    def test_streaming_off(self, tmp_path):
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["channels"]["telegram"]["streaming"] == "off"

    def test_no_agent_instructions_key(self, tmp_path):
        """Agent list entries should NOT have an instructions key (OpenClaw rejects it)."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        agent = cfg["agents"]["list"][0]
        assert "instructions" not in agent

    def test_group_with_topics(self, tmp_path):
        """When group_id and topic_ids are given, topics are configured."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
            group_id="-1001234567890",
            topic_ids={
                "status": "100",
                "maintenance": "101",
                "alerts": "102",
                "prs": "103",
                "chat": "104",
            },
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        grp = cfg["channels"]["telegram"]["groups"]["-1001234567890"]
        assert grp["requireMention"] is False
        topics = grp["topics"]
        assert topics["1"]["enabled"] is False
        assert topics["100"]["requireMention"] is False
        assert "STATUS" in topics["100"]["systemPrompt"]
        assert topics["101"]["requireMention"] is False
        assert topics["104"]["requireMention"] is False
        assert "CHAT" in topics["104"]["systemPrompt"]

    def test_group_general_disabled(self, tmp_path):
        """General topic (thread 1) is disabled when group is configured."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
            group_id="-100999",
            topic_ids={"status": "10"},
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        topics = cfg["channels"]["telegram"]["groups"]["-100999"]["topics"]
        assert topics["1"]["enabled"] is False

    def test_no_group_id_means_empty_groups(self, tmp_path):
        """Without group_id, groups config is empty."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=999,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        assert cfg["channels"]["telegram"]["groups"] == {}

    def test_owner_id_in_allowlists(self, tmp_path):
        """Owner ID appears in both DM and group allowlists."""
        write_openclaw_config(
            openclaw_dir=tmp_path,
            kimi_key="sk-test",
            bot_token="123:ABC",
            owner_id=2045995148,
        )
        cfg = json.loads((tmp_path / "openclaw.json").read_text())
        tg = cfg["channels"]["telegram"]
        assert "2045995148" in tg["allowFrom"]
        assert "2045995148" in tg["groupAllowFrom"]
