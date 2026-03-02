"""Check installed versions of all dependencies."""

from __future__ import annotations

import subprocess

_VERSION_COMMANDS = {
    "gt": ["gt", "--version"],
    "claude": ["claude", "--version"],
    "openclaw": ["openclaw", "--version"],
    "dolt": ["dolt", "version"],
    "kimigas": ["kimigas", "--version"],
}


def check_versions() -> dict[str, str]:
    """Get version strings for all dependencies.

    Returns:
        Dict mapping dependency name to version string or "not installed".
    """
    versions: dict[str, str] = {}
    for name, cmd in _VERSION_COMMANDS.items():
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0:
                versions[name] = result.stdout.decode().strip()
            else:
                versions[name] = "not installed"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            versions[name] = "not installed"
    return versions
