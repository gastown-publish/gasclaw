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
    owner_id: str,
    gateway_port: int = 18789,
) -> Path:
    """Write ~/.openclaw/openclaw.json with full configuration.

    Args:
        openclaw_dir: Path to the openclaw config directory.
        kimi_key: Kimi API key for OpenClaw's own LLM.
        bot_token: Telegram bot token.
        owner_id: Telegram user ID for allowlist.
        gateway_port: Gateway port (default 18789).

    Returns:
        Path to the written openclaw.json.
    """
    openclaw_dir.mkdir(parents=True, exist_ok=True)

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
                }
            ],
        },
        "channels": {
            "telegram": {
                "botToken": bot_token,
                "dmPolicy": "allowlist",
                "allowFrom": [owner_id],
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
                "token": _generate_auth_token(),
            },
        },
        "tools": {
            "exec": {
                "security": "full",
            },
        },
        "env": {
            "MOONSHOT_API_KEY": kimi_key,
        },
    }

    config_path = openclaw_dir / "openclaw.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config_path
