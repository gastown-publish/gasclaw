"""OpenClaw configuration writer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _generate_auth_token() -> str:
    """Generate a random 64-char hex token."""
    return hashlib.sha256(os.urandom(32)).hexdigest()


__all__ = ["write_openclaw_config"]


def write_openclaw_config(
    *,
    openclaw_dir: Path,
    kimi_key: str,
    bot_token: str,
    owner_id: int,
    group_id: str = "",
    topic_ids: dict[str, str] | None = None,
    gateway_port: int = 18789,
    gt_root: str = "/workspace/gt",
    agent_count: int = 1,  # Number of agents to create (#322)
) -> Path:
    """Write ~/.openclaw/openclaw.json with full configuration.

    Uses beads (bd) for memory/state instead of file-based memory.
    Supports Telegram forum topics to keep different message types
    in separate threads (Status, Maintenance, Alerts, PRs, Chat).

    Args:
        openclaw_dir: Path to the openclaw config directory.
        kimi_key: Kimi API key for OpenClaw's own LLM.
        bot_token: Telegram bot token.
        owner_id: Telegram user ID for allowlist.
        group_id: Telegram group/supergroup chat ID.
        topic_ids: Mapping of topic names to thread IDs.
        gateway_port: Gateway port (default 18789).
        gt_root: Gastown root directory (for bead workspace).
        agent_count: Number of agents to create in the config.

    Returns:
        Path to the written openclaw.json.

    """
    openclaw_dir.mkdir(parents=True, exist_ok=True)

    config_path = openclaw_dir / "openclaw.json"
    topics = topic_ids or {}

    auth_token = _generate_auth_token()
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
            auth_token = (
                existing.get("gateway", {}).get("auth", {}).get("token", auth_token)
            )
        except (json.JSONDecodeError, OSError):
            pass

    owner_str = str(owner_id)

    # Topic routing: each bot responds only in its own topic.
    own_topic = os.environ.get("GASCLAW_OWN_TOPIC")
    all_topic_ids = os.environ.get("GASCLAW_ALL_TOPICS", "1,918,919,920,921,1425").split(",")
    group_topics: dict[str, Any] = {}
    for tid in all_topic_ids:
        tid = tid.strip()
        if not tid: continue
        is_own = own_topic and tid == own_topic.strip()
        group_topics[tid] = {"requireMention": not is_own}
    groups_cfg: dict[str, Any] = {}
    if group_id:
        groups_cfg[group_id] = {
            "requireMention": True,
            "groupPolicy": "open",
            "topics": group_topics,
        }

    # Use anthropic provider pointed at local LiteLLM (MiniMax M2.7 backend)
    primary_model = "anthropic/claude-sonnet-4-6"
    fallback_models: list = []
    litellm_base_url = os.environ.get("LITELLM_BASE_URL", "http://10.91.141.1:4000")
    litellm_api_key = os.environ.get("ANTHROPIC_API_KEY", kimi_key)

    # Build agent list based on agent_count (#322)
    agent_list = []
    for i in range(agent_count):
        agent_id = f"crew-{i}" if i > 0 else "main"
        agent_name = f"Gasclaw Crew-{i}" if i > 0 else "Gasclaw Overseer"
        agent_list.append({
            "id": agent_id,
            "identity": {
                "name": agent_name,
                "emoji": "🏭",
            },
        })

    config = {
        "agents": {
            "defaults": {
                "model": {
                    "primary": primary_model,
                    "fallbacks": fallback_models,
                },
                "models": {
                    primary_model: {},
                    "openrouter/qwen/qwen3-coder:free": {},
                },
                "workspace": str(openclaw_dir / "workspace"),
            },
            "list": agent_list,
        },
        "models": {
            "providers": {
                "anthropic": {
                    "baseUrl": litellm_base_url,
                    "auth": "api-key",
                    "apiKey": litellm_api_key,
                    "models": [
                        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6"}
                    ],
                },
            },
        },
        "channels": {
            "telegram": {
                "enabled": True,
                "botToken": bot_token,
                "dmPolicy": "allowlist",
                "allowFrom": [owner_str],
                "groupPolicy": "allowlist",
                "groupAllowFrom": [owner_str],
                "groups": groups_cfg,
                "streaming": "off",
            },
        },
        "messages": {
            "ackReactionScope": "none",
            "ackReaction": "",
        },
        "commands": {
            "native": "auto",
            "nativeSkills": "auto",
            "restart": True,
            "ownerDisplay": "raw",
        },
        "gateway": {
            "port": gateway_port,
            "mode": "local",
            "bind": "lan",
            "auth": {
                "mode": "token",
                "token": auth_token,
            },
        },
        "plugins": {
            "slots": {
                "memory": "memory-lancedb",
            },
            "entries": {
                "memory-lancedb": {
                    "enabled": True,
                    "config": {
                        "embedding": {
                            "apiKey": litellm_api_key,
                            "model": "text-embedding-3-small",
                            "baseUrl": (litellm_base_url + "/v1") if not litellm_base_url.endswith("/v1") else litellm_base_url,
                            "dimensions": 256,
                        },
                        "autoCapture": True,
                        "autoRecall": True,
                    },
                },
                "active-memory": {"enabled": True},
            },
        },
        "tools": {
            "exec": {
                "security": "full",
            },
        },
        "env": {
            "ANTHROPIC_API_KEY": litellm_api_key,
            "ANTHROPIC_BASE_URL": litellm_base_url,
            "MOONSHOT_API_KEY": kimi_key,
            "BD_ROOT": gt_root,
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    return config_path
