"""Apply updates to all dependencies."""

from __future__ import annotations

import subprocess

_UPDATE_COMMANDS = {
    "gt": ["gt", "self-update"],
    "openclaw": ["npm", "update", "-g", "openclaw"],
    "claude": ["npm", "update", "-g", "@anthropic-ai/claude-code"],
    "kimigas": ["pip", "install", "--upgrade", "kimi-cli"],
}


def apply_updates() -> dict[str, str]:
    """Run update commands for all dependencies.

    Returns:
        Dict mapping dependency name to result string.
    """
    results: dict[str, str] = {}
    for name, cmd in _UPDATE_COMMANDS.items():
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode == 0:
                results[name] = "updated"
            else:
                stderr = result.stderr.decode().strip()[:200]
                results[name] = f"failed: {stderr}"
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            results[name] = f"error: {e}"
    return results
