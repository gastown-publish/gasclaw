"""OpenClaw configuration writer."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


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
    gateway_port: int = 18789,
    gt_root: str = "/workspace/gt",
) -> Path:
    """Write ~/.openclaw/openclaw.json with full configuration.

    Uses beads (bd) for memory/state instead of file-based memory.
    The workspace points to the Gastown rig's .beads directory so
    OpenClaw tracks all state through Dolt-backed beads.

    Args:
        openclaw_dir: Path to the openclaw config directory.
        kimi_key: Kimi API key for OpenClaw's own LLM.
        bot_token: Telegram bot token.
        owner_id: Telegram user ID for allowlist.
        gateway_port: Gateway port (default 18789).
        gt_root: Gastown root directory (for bead workspace).

    Returns:
        Path to the written openclaw.json.

    """
    openclaw_dir.mkdir(parents=True, exist_ok=True)

    config_path = openclaw_dir / "openclaw.json"

    # Preserve existing auth token to avoid breaking client integrations
    auth_token = _generate_auth_token()
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
            auth_token = existing.get("gateway", {}).get("auth", {}).get("token", auth_token)
        except (json.JSONDecodeError, OSError):
            pass

    config = {
        "agents": {
            "defaults": {
                "model": {
                    "primary": "openrouter/moonshotai/kimi-k2.5",
                    "fallbacks": ["openrouter/qwen/qwen3-coder:free"],
                },
                "models": {
                    "openrouter/moonshotai/kimi-k2.5": {},
                    "openrouter/qwen/qwen3-coder:free": {},
                },
                "workspace": str(openclaw_dir / "workspace"),
            },
            "list": [
                {
                    "id": "main",
                    "identity": {
                        "name": "Gasclaw Overseer",
                        "emoji": "🏭",
                    },
                    "instructions": (
                        "You use beads (bd CLI) for ALL memory and state tracking. "
                        "Never use plain markdown memory files. "
                        "Use 'bd create' to record tasks, decisions, and state. "
                        "Use 'bd list' and 'bd search' to recall past context. "
                        "Use 'bd close' when tasks are done. "
                        "Beads are backed by Dolt SQL and survive restarts."
                    ),
                }
            ],
        },
        "channels": {
            "telegram": {
                "botToken": bot_token,
                "dmPolicy": "allowlist",
                "allowFrom": [str(owner_id)],
            },
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
            "MOONSHOT_API_KEY": kimi_key,
            "BD_ROOT": gt_root,
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    return config_path
