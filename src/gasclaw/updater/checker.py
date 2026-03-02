"""Check installed versions of all dependencies."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

_VERSION_COMMANDS = {
    "gt": ["gt", "--version"],
    "claude": ["claude", "--version"],
    "openclaw": ["openclaw", "--version"],
    "dolt": ["dolt", "version"],
    "kimigas": ["kimigas", "--version"],
}

__all__ = ["check_versions"]


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
                logger.debug("%s version: %s", name, versions[name])
            else:
                versions[name] = "not installed"
                logger.warning("%s returned non-zero exit code: %d", name, result.returncode)
        except FileNotFoundError:
            versions[name] = "not installed"
            logger.debug("%s not found in PATH", name)
        except subprocess.TimeoutExpired:
            versions[name] = "not installed"
            logger.warning("%s version check timed out", name)
    return versions
