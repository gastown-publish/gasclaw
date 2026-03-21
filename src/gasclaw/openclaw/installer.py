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

    # General topic (1) must stay enabled for inbound message routing
    group_topics: dict[str, Any] = {"1": {"requireMention": False}}
    topic_prompts = {
        "status": "STATUS topic. Post system health, dashboards, service status.",
        "maintenance": "MAINTENANCE topic. Post cycle reports, config changes, update logs.",
        "alerts": "ALERTS topic. Only urgent: service down, test failures, security.",
        "prs": "PRs & ISSUES topic. PR reviews, merges, issue updates, releases.",
        "chat": "CHAT topic. Conversations with the owner. Answer questions here.",
    }
    for name, prompt in topic_prompts.items():
        tid = topics.get(name, "")
        if tid:
            group_topics[tid] = {
                "requireMention": False,
                "systemPrompt": prompt,
            }

    # Build groups config
    groups_cfg: dict[str, Any] = {}
    if group_id:
        groups_cfg[group_id] = {
            "requireMention": False,
            "groupPolicy": "open",
            "topics": group_topics,
        }

    # Correct model ID for kimi-coding provider (#320)
    primary_model = "kimi-coding/k2p5"
    fallback_models = ["openrouter/qwen/qwen3-coder:free"]

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
                "memory": "none",
            },
        },
        "tools": {
            "exec": {
                "security": "full",
            },
        },
        "env": {
            # KIMI_API_KEY required for kimi-coding provider (#323)
            "KIMI_API_KEY": kimi_key,
            "MOONSHOT_API_KEY": kimi_key,
            "BD_ROOT": gt_root,
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    return config_path
