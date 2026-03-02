"""Configuration loading and validation from environment variables."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

__all__ = ["GasclawConfig", "load_config"]

logger = logging.getLogger(__name__)


@dataclass
class GasclawConfig:
    """Gasclaw configuration loaded from environment variables."""

    # Required
    gastown_kimi_keys: list[str]
    openclaw_kimi_key: str
    telegram_bot_token: str
    telegram_owner_id: str

    # Optional with defaults
    gt_rig_url: str = "/project"
    project_dir: str = "/project"  # Directory for git activity checks
    gt_agent_count: int = 6
    monitor_interval: int = 300  # seconds between health checks
    activity_deadline: int = 3600  # seconds — must see a push/PR within this window


def _require_env(name: str) -> str:
    """Get a required environment variable or raise ValueError."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value


def _parse_keys(raw: str) -> list[str]:
    """Parse colon-separated keys, filtering empty segments."""
    return [k.strip() for k in raw.split(":") if k.strip()]


def _parse_positive_int(value: str, default: int, name: str = "") -> int:
    """Parse a positive integer, returning default if invalid.

    Args:
        value: The string value to parse.
        default: The default to return if parsing fails or value is not positive.
        name: The name of the config variable (for warning messages).

    Returns:
        The parsed positive integer, or default if invalid.
    """
    try:
        result = int(value)
        if result <= 0:
            if name:
                logger.warning(
                    "Invalid %s: %r must be positive, using default %d",
                    name, value, default
                )
            return default
        return result
    except (ValueError, TypeError):
        if name:
            logger.warning(
                "Invalid %s: %r is not a valid integer, using default %d",
                name, value, default
            )
        return default


def load_config() -> GasclawConfig:
    """Load and validate configuration from environment variables."""
    raw_keys = _require_env("GASTOWN_KIMI_KEYS")
    keys = _parse_keys(raw_keys)
    if not keys:
        raise ValueError("GASTOWN_KIMI_KEYS contains no valid keys")

    return GasclawConfig(
        gastown_kimi_keys=keys,
        openclaw_kimi_key=_require_env("OPENCLAW_KIMI_KEY"),
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_owner_id=_require_env("TELEGRAM_OWNER_ID"),
        gt_rig_url=os.environ.get("GT_RIG_URL", "/project").strip() or "/project",
        project_dir=os.environ.get("PROJECT_DIR", "/project").strip() or "/project",
        gt_agent_count=_parse_positive_int(
            os.environ.get("GT_AGENT_COUNT", "6"), 6, "GT_AGENT_COUNT"
        ),
        monitor_interval=_parse_positive_int(
            os.environ.get("MONITOR_INTERVAL", "300"), 300, "MONITOR_INTERVAL"
        ),
        activity_deadline=_parse_positive_int(
            os.environ.get("ACTIVITY_DEADLINE", "3600"), 3600, "ACTIVITY_DEADLINE"
        ),
    )
