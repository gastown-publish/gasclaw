"""Build environment variables for proxying Claude Code through Kimi."""

from __future__ import annotations

import json
from pathlib import Path

KIMI_ANTHROPIC_BASE_URL = "https://api.kimi.com/coding/"
_DEFAULT_CONFIG_DIR = str(Path.home() / ".claude-kimigas")

__all__ = [
    "KIMI_ANTHROPIC_BASE_URL",
    "build_claude_env",
    "write_claude_config",
]


def build_claude_env(api_key: str, *, config_dir: str | None = None) -> dict[str, str]:
    """Build env dict that makes Claude Code use Kimi K2.5 backend.

    Args:
        api_key: Kimi API key.
        config_dir: Isolated Claude config directory. Defaults to ~/.claude-kimigas.

    Returns:
        dict of environment variables to set/override.

    """
    return {
        "ANTHROPIC_BASE_URL": KIMI_ANTHROPIC_BASE_URL,
        "ANTHROPIC_API_KEY": api_key,
        "CLAUDE_CONFIG_DIR": config_dir or _DEFAULT_CONFIG_DIR,
        "DISABLE_COST_WARNINGS": "true",
    }


def write_claude_config(api_key: str, *, config_dir: str | None = None) -> Path:
    """Write Claude Code config files for headless Kimi-backed operation.

    Sets ``bypassPermissionsModeAccepted`` so agents run without the
    ``--dangerously-skip-permissions`` flag (which is rejected under root).
    Also pre-approves the Kimi API key fingerprint and marks onboarding done.

    Args:
        api_key: Kimi API key (last 20 chars used as fingerprint).
        config_dir: Claude config directory. Defaults to ~/.claude-kimigas.

    Returns:
        Path to the config directory.

    """
    cfg_dir = Path(config_dir or _DEFAULT_CONFIG_DIR)
    cfg_dir.mkdir(parents=True, exist_ok=True)

    (cfg_dir / ".credentials.json").write_text("{}")

    fingerprint = api_key[-20:] if len(api_key) >= 20 else api_key
    claude_cfg = {
        "hasCompletedOnboarding": True,
        "bypassPermissionsModeAccepted": True,
        "customApiKeyResponses": {"approved": [fingerprint]},
    }
    (cfg_dir / ".claude.json").write_text(json.dumps(claude_cfg, indent=2))

    return cfg_dir
