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
                logger.debug(f"{name} version: {versions[name]}")
            else:
                versions[name] = "not installed"
                logger.warning(f"{name} returned non-zero exit code: {result.returncode}")
        except FileNotFoundError:
            versions[name] = "not installed"
            logger.debug(f"{name} not found in PATH")
        except subprocess.TimeoutExpired:
            versions[name] = "not installed"
            logger.warning(f"{name} version check timed out")
    return versions
