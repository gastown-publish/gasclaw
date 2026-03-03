"""Write Gastown settings/config.json for kimi-claude agent."""

from __future__ import annotations

import json
from pathlib import Path

__all__ = ["write_agent_config"]

_CONFIG_TEMPLATE = {
    "type": "town-settings",
    "version": 1,
    "default_agent": "kimi-claude",
    "agents": {
        "kimi-claude": {
            "command": "kimigas",
            "args": ["run", "claude", "--yolo"],
        }
    },
}


def write_agent_config(gt_root: Path) -> Path:
    """Write the Gastown agent configuration file.

    Args:
        gt_root: Root directory of the Gastown installation (e.g. /workspace/gt).

    Returns:
        Path to the written config.json.

    """
    settings_dir = gt_root / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    config_path = settings_dir / "config.json"
    config_path.write_text(json.dumps(_CONFIG_TEMPLATE, indent=2))
    return config_path
