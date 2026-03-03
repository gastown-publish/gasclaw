"""OpenClaw authentication utilities."""

from __future__ import annotations

import json
import logging
from pathlib import Path

__all__ = ["get_gateway_auth_token"]

logger = logging.getLogger(__name__)


def get_gateway_auth_token(openclaw_dir: Path | None = None) -> str:
    """Read the gateway auth token from openclaw.json config.

    Args:
        openclaw_dir: Path to the openclaw config directory.
            Defaults to ~/.openclaw

    Returns:
        The auth token string, or empty string if not found.

    """
    if openclaw_dir is None:
        openclaw_dir = Path.home() / ".openclaw"

    config_path = openclaw_dir / "openclaw.json"

    if not config_path.exists():
        logger.warning("openclaw.json not found at %s", config_path)
        return ""

    try:
        config = json.loads(config_path.read_text())
        token = config.get("gateway", {}).get("auth", {}).get("token", "")
        if token:
            logger.debug("Read auth token from %s", config_path)
        else:
            logger.warning("No auth token found in %s", config_path)
        return token
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in %s: %s", config_path, e)
        return ""
    except OSError as e:
        logger.error("Error reading %s: %s", config_path, e)
        return ""
