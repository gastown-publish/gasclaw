"""Build environment variables for proxying Claude Code through Kimi."""

from __future__ import annotations

from pathlib import Path

KIMI_ANTHROPIC_BASE_URL = "https://api.kimi.com/coding/"
_DEFAULT_CONFIG_DIR = str(Path.home() / ".claude-kimigas")

__all__ = ["KIMI_ANTHROPIC_BASE_URL", "build_claude_env"]


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
