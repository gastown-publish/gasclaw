"""Configuration loading and validation from environment variables.

Supports YAML config files for non-secret settings. Secrets must still
be provided via environment variables.

Config file search order (first found wins):
1. Path from GASCLAW_CONFIG env var
2. /workspace/config/gasclaw.yaml (for maintainer mode)
3. ./gasclaw.yaml (for local development)

Env vars always override YAML config values.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = ["GasclawConfig", "load_config", "load_yaml_config", "merge_config"]

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
    dolt_port: int = 3307  # Port for dolt SQL server
    gateway_port: int = 18789  # Port for OpenClaw gateway

    # Telegram allowlists (parsed from colon-separated env vars)
    telegram_allow_ids: list[str] = None  # type: ignore[assignment]
    telegram_group_ids: list[str] = None  # type: ignore[assignment]

    # Agent identity customization
    agent_id: str = "main"
    agent_name: str = "Gasclaw Overseer"
    agent_emoji: str = "🏭"

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Initialize empty lists for optional allowlists
        if self.telegram_allow_ids is None:
            self.telegram_allow_ids = []
        if self.telegram_group_ids is None:
            self.telegram_group_ids = []

        # Validate telegram_owner_id is numeric
        if self.telegram_owner_id and not self.telegram_owner_id.isdigit():
            raise ValueError(f"TELEGRAM_OWNER_ID must be numeric, got: {self.telegram_owner_id}")

        # Validate additional allowlist IDs are numeric
        for uid in self.telegram_allow_ids:
            if not uid.isdigit():
                raise ValueError(f"TELEGRAM_ALLOW_IDS must be numeric, got: {uid}")

        # Validate group IDs are numeric (can be negative for groups)
        for gid in self.telegram_group_ids:
            if not gid.lstrip("-").isdigit():
                raise ValueError(f"TELEGRAM_GROUP_IDS must be numeric, got: {gid}")

        # Validate telegram_bot_token format (should be digits:alphanumeric)
        if self.telegram_bot_token and not re.match(r"^\d+:[\w-]+$", self.telegram_bot_token):
            raise ValueError(
                f"TELEGRAM_BOT_TOKEN must be in format 'digits:alphanumeric', "
                f"got: {self.telegram_bot_token[:10]}..."
            )

        # Validate Kimi key format (should start with sk-)
        for i, key in enumerate(self.gastown_kimi_keys):
            if not key.startswith("sk-"):
                raise ValueError(
                    f"GASTOWN_KIMI_KEYS[{i}] must start with 'sk-', got: {key[:10]}..."
                )

        if self.openclaw_kimi_key and not self.openclaw_kimi_key.startswith("sk-"):
            raise ValueError(
                f"OPENCLAW_KIMI_KEY must start with 'sk-', got: {self.openclaw_kimi_key[:10]}..."
            )

        # Validate paths are absolute
        if self.project_dir and not self.project_dir.startswith("/"):
            logger.warning("PROJECT_DIR should be an absolute path, got: %s", self.project_dir)

        # Validate gt_rig_url
        if self.gt_rig_url and not self.gt_rig_url.startswith(("/", "http", "https")):
            logger.warning("GT_RIG_URL should be a path or URL, got: %s", self.gt_rig_url)


def _require_env(name: str) -> str:
    """Get a required environment variable or raise ValueError."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable {name} is not set")
    return value


def _parse_keys(raw: str) -> list[str]:
    """Parse colon-separated keys, filtering empty segments."""
    return [k.strip() for k in raw.split(":") if k.strip()]


def _parse_ids(raw: str) -> list[str]:
    """Parse colon-separated IDs, filtering empty segments."""
    return [id.strip() for id in raw.split(":") if id.strip()]


def _parse_positive_int(value: str, default: int, name: str = "") -> int:
    """Parse a positive integer, returning default if invalid.

    Only decimal integers are supported. Octal (0o), hexadecimal (0x),
    and binary (0b) prefixes are not recognized - the value is parsed
    as base-10. Leading zeros are ignored (e.g., "007" becomes 7).

    Args:
        value: The string value to parse (decimal only).
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
                    "Invalid %s: %r must be positive, using default %d", name, value, default
                )
            return default
        return result
    except (ValueError, TypeError):
        if name:
            logger.warning(
                "Invalid %s: %r is not a valid integer, using default %d", name, value, default
            )
        return default


def _parse_port(value: str, default: int, name: str = "") -> int:
    """Parse a TCP/UDP port number (1-65535), returning default if invalid.

    Unlike _parse_positive_int, this function enforces the valid port range.
    Invalid values are logged and the default is returned.

    Args:
        value: The string value to parse.
        default: The default to return if parsing fails or value is out of range.
        name: The name of the config variable (for warning messages).

    Returns:
        The parsed port number, or default if invalid.

    """
    try:
        result = int(value)
        if result < 1 or result > 65535:
            if name:
                logger.warning(
                    "Invalid %s: %r must be between 1 and 65535, using default %d",
                    name,
                    value,
                    default,
                )
            return default
        return result
    except (ValueError, TypeError):
        if name:
            logger.warning(
                "Invalid %s: %r is not a valid integer, using default %d", name, value, default
            )
        return default


def _get_yaml_value(yaml_cfg: dict, *keys: str, default: Any = None) -> Any:
    """Get a nested value from YAML config by key path."""
    current = yaml_cfg
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def load_yaml_config(path: str | None = None) -> dict:
    """Load YAML config file, returning empty dict if not found or invalid.

    Args:
        path: Path to YAML file. If None, uses GASCLAW_CONFIG env var or
              defaults to /workspace/config/gasclaw.yaml.

    Returns:
        Parsed YAML config dict, or empty dict if file not found/invalid.
    """
    if path is None:
        path = os.environ.get("GASCLAW_CONFIG", "/workspace/config/gasclaw.yaml")

    if not path or not os.path.exists(path):
        return {}

    try:
        # Try PyYAML first
        try:
            import yaml

            with open(path) as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            # Fallback to minimal parser for simple YAML
            return _parse_simple_yaml(Path(path).read_text())
    except Exception as e:
        logger.warning("Failed to parse YAML config at %s: %s", path, e)
        return {}


def _parse_simple_yaml(text: str) -> dict:
    """Minimal YAML parser for simple key: value files (no PyYAML needed)."""
    result: dict = {}
    current_section = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Section header: "section:"
        if not line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1]
            result[current_section] = {}
            continue

        # Key-value pair in section
        if current_section and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()

            # Parse value
            if val.startswith("[") and val.endswith("]"):
                # List: ["a", "b"] or [a, b]
                val = [v.strip().strip('"').strip("'") for v in val[1:-1].split(",") if v.strip()]
            elif val.startswith('"') and val.endswith('"') or \
                    val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            elif val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.isdigit() or (val.startswith("-") and val[1:].isdigit()):
                val = int(val)
            elif val == "":
                val = None

            result[current_section][key] = val

    return result


def merge_config(
    yaml_cfg: dict,
    env_value: str | None,
    yaml_keys: tuple[str, ...],
    default: Any,
    parser: callable = lambda x: x,  # type: ignore
    name: str = "",
) -> Any:
    """Merge YAML and env var values, with env vars taking precedence.

    Args:
        yaml_cfg: Parsed YAML config dict
        env_value: Environment variable value (or None if not set)
        yaml_keys: Key path to look up in YAML (e.g., ("gastown", "agent_count"))
        default: Default value if neither YAML nor env var set
        parser: Function to parse the value (e.g., int, str.strip)
        name: Config name for logging/warnings

    Returns:
        Merged configuration value
    """
    # Env var always wins
    if env_value is not None and env_value.strip():
        try:
            return parser(env_value.strip())
        except (ValueError, TypeError):
            pass  # Fall through to YAML/default

    # Check YAML
    yaml_val = _get_yaml_value(yaml_cfg, *yaml_keys)
    if yaml_val is not None:
        try:
            return parser(yaml_val)
        except (ValueError, TypeError):
            pass  # Fall through to default

    return default


def _parse_port_yaml(value: Any, default: int, name: str = "") -> int:
    """Parse port from YAML or env var, with validation."""
    try:
        port = int(value)
        if 1 <= port <= 65535:
            return port
    except (ValueError, TypeError):
        pass

    if name:
        logger.warning(
            "Invalid %s: %r must be between 1 and 65535, using default %d",
            name, value, default,
        )
    return default


def _parse_positive_int_yaml(value: Any, default: int, name: str = "") -> int:
    """Parse positive int from YAML or env var, with validation.

    Matches the behavior of _parse_positive_int for backward compatibility.
    """
    try:
        result = int(value)
        if result <= 0:
            if name:
                logger.warning(
                    "Invalid %s: %r must be positive, using default %d", name, value, default
                )
            return default
        return result
    except (ValueError, TypeError):
        if name:
            logger.warning(
                "Invalid %s: %r is not a valid integer, using default %d", name, value, default
            )
        return default


def _parse_string_yaml(value: Any, default: str = "") -> str:
    """Parse string from YAML or env var.

    Note: default is required when called from merge_config, but we handle
    the default in merge_config itself, so this just parses the value.
    """
    if value is None:
        return default
    result = str(value).strip()
    return result if result else default


def _parse_string_list_yaml(value: Any) -> list[str]:
    """Parse list of strings from YAML."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None]
    if isinstance(value, str):
        return [v.strip() for v in value.split(":") if v.strip()]
    return []


def load_config(config_path: str | None = None) -> GasclawConfig:
    """Load and validate configuration from environment variables and YAML file.

    Args:
        config_path: Optional path to YAML config file. If not provided,
                     uses GASCLAW_CONFIG env var or default path.

    Returns:
        GasclawConfig with merged env var and YAML values.

    Priority (highest to lowest):
    1. Environment variables
    2. YAML config file
    3. Default values
    """
    # Load YAML config
    yaml_cfg = load_yaml_config(config_path)

    # Required env vars (no YAML fallback for secrets)
    raw_keys = _require_env("GASTOWN_KIMI_KEYS")
    keys = _parse_keys(raw_keys)
    if not keys:
        raise ValueError("GASTOWN_KIMI_KEYS contains no valid keys")

    # Parse additional Telegram allowlists from env var (colon-separated)
    env_allow_ids = _parse_ids(os.environ.get("TELEGRAM_ALLOW_IDS", ""))
    env_group_ids = _parse_ids(os.environ.get("TELEGRAM_GROUP_IDS", ""))

    # Parse from YAML (list format)
    yaml_allow_ids = _parse_string_list_yaml(_get_yaml_value(yaml_cfg, "telegram", "allow_ids"))
    yaml_group_ids = _parse_string_list_yaml(_get_yaml_value(yaml_cfg, "telegram", "group_ids"))

    # Merge allowlists (env var takes precedence, falls back to YAML)
    telegram_allow_ids = env_allow_ids if env_allow_ids else yaml_allow_ids
    telegram_group_ids = env_group_ids if env_group_ids else yaml_group_ids

    # Build config with merge priority: env vars > YAML > defaults
    config = GasclawConfig(
        gastown_kimi_keys=keys,
        openclaw_kimi_key=_require_env("OPENCLAW_KIMI_KEY"),
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_owner_id=_require_env("TELEGRAM_OWNER_ID"),
        # Gastown settings
        gt_rig_url=merge_config(
            yaml_cfg,
            os.environ.get("GT_RIG_URL"),
            ("gastown", "rig_url"),
            "/project",
            _parse_string_yaml,
        ),
        # Paths
        project_dir=merge_config(
            yaml_cfg,
            os.environ.get("PROJECT_DIR"),
            ("paths", "project_dir"),
            "/project",
            _parse_string_yaml,
        ),
        # Gastown settings
        gt_agent_count=_parse_positive_int_yaml(
            os.environ.get("GT_AGENT_COUNT") or _get_yaml_value(yaml_cfg, "gastown", "agent_count"),
            6,
            "GT_AGENT_COUNT" if os.environ.get("GT_AGENT_COUNT") else "gastown.agent_count",  # noqa: E501
        ),
        # Maintenance settings
        monitor_interval=_parse_positive_int_yaml(
            os.environ.get("MONITOR_INTERVAL")  # noqa: E501
            or _get_yaml_value(yaml_cfg, "maintenance", "monitor_interval"),
            300,
            "MONITOR_INTERVAL" if os.environ.get("MONITOR_INTERVAL") else "maintenance.monitor_interval",  # noqa: E501
        ),
        activity_deadline=_parse_positive_int_yaml(
            os.environ.get("ACTIVITY_DEADLINE")  # noqa: E501
            or _get_yaml_value(yaml_cfg, "maintenance", "activity_deadline"),
            3600,
            "ACTIVITY_DEADLINE" if os.environ.get("ACTIVITY_DEADLINE") else "maintenance.activity_deadline",  # noqa: E501
        ),
        # Service ports
        dolt_port=_parse_port_yaml(
            os.environ.get("DOLT_PORT") or _get_yaml_value(yaml_cfg, "services", "dolt_port"),
            3307,
            "DOLT_PORT" if os.environ.get("DOLT_PORT") else "services.dolt_port",
        ),
        gateway_port=_parse_port_yaml(
            os.environ.get("GATEWAY_PORT") or _get_yaml_value(yaml_cfg, "services", "gateway_port"),
            18789,
            "GATEWAY_PORT" if os.environ.get("GATEWAY_PORT") else "services.gateway_port",
        ),
        # Telegram allowlists
        telegram_allow_ids=telegram_allow_ids,
        telegram_group_ids=telegram_group_ids,
        # Agent identity
        agent_id=merge_config(
            yaml_cfg,
            os.environ.get("AGENT_ID"),
            ("agent", "id"),
            "main",
            _parse_string_yaml,
        ),
        agent_name=merge_config(
            yaml_cfg,
            os.environ.get("AGENT_NAME"),
            ("agent", "name"),
            "Gasclaw Overseer",
            _parse_string_yaml,
        ),
        agent_emoji=merge_config(
            yaml_cfg,
            os.environ.get("AGENT_EMOJI"),
            ("agent", "emoji"),
            "🏭",
            _parse_string_yaml,
        ),
    )

    logger.debug("Loaded configuration with %d Gastown keys", len(keys))
    return config
