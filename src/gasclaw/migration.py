"""Migration utilities for transitioning from Gastown to gasclaw.

This module provides functionality to detect existing Gastown installations
and migrate their configuration to gasclaw format.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from gasclaw.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_GASTOWN_DIRS = [Path.home() / ".gt", Path.home() / ".gastown"]
DEFAULT_OPENCLAW_DIR = Path.home() / ".openclaw"
DEFAULT_OPENCLAW_LAUNCHER_DIR = Path.home() / "openclaw-launcher"
DEFAULT_GASCLAW_ENV = Path("/workspace/.env")


@dataclass
class MigrationResult:
    """Result of a migration attempt."""

    success: bool
    dry_run: bool
    gastown_detected: bool
    backup_path: Path | None = None
    migrated_keys: list[str] = field(default_factory=list)
    env_file_path: Path | None = None
    error_message: str = ""

    def summary(self) -> str:
        """Return a human-readable summary of the migration."""
        lines = []

        if self.dry_run:
            lines.append("🔄 DRY RUN - No changes were made")
            lines.append("")

        if self.success:
            lines.append("✅ Migration successful")
            lines.append(f"   Detected Gastown: {self.gastown_detected}")
            if self.backup_path:
                lines.append(f"   Backup created: {self.backup_path}")
            if self.migrated_keys:
                lines.append(f"   Migrated keys: {', '.join(self.migrated_keys)}")
            elif self.dry_run:
                lines.append("   Migrated keys: (will be determined during actual migration)")
            if self.env_file_path:
                lines.append(f"   Config file: {self.env_file_path}")
        else:
            lines.append("❌ Migration failed")
            if self.error_message:
                lines.append(f"   Error: {self.error_message}")

        return "\n".join(lines)


def detect_gastown_setup(
    search_dirs: list[Path] | Path | None = None,
) -> dict[str, Any]:
    """Detect if Gastown is installed and configured.

    Checks for:
    1. KIMI_API_KEY environment variable (classic Gastown)
    2. Gastown config files in ~/.gt or ~/.gastown

    Args:
        search_dirs: Directories to search for Gastown configs.

    Returns:
        Dict with detection results including detected status and source.

    """
    # If gasclaw config already exists, don't offer migration
    if os.environ.get("GASTOWN_KIMI_KEYS"):
        return {
            "detected": False,
            "reason": "gasclaw_config_already_exists",
            "message": "Gasclaw configuration already exists (GASTOWN_KIMI_KEYS is set)",
        }

    # Check for classic Gastown environment variable
    kimi_api_key = os.environ.get("KIMI_API_KEY", "").strip()
    if kimi_api_key:
        return {
            "detected": True,
            "source": "env_var",
            "kimi_api_key": kimi_api_key,
            "message": "Found KIMI_API_KEY environment variable",
        }

    # Search for Gastown config directories
    dirs_to_search = []
    if search_dirs is None:
        dirs_to_search = DEFAULT_GASTOWN_DIRS
    elif isinstance(search_dirs, Path):
        dirs_to_search = [search_dirs]
    else:
        dirs_to_search = search_dirs

    for gt_dir in dirs_to_search:
        config_file = gt_dir / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                return {
                    "detected": True,
                    "source": "config_file",
                    "config_dir": str(gt_dir),
                    "config": config,
                    "message": f"Found Gastown config at {config_file}",
                }
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Found config file but couldn't read it: %s", e)
                continue

    return {
        "detected": False,
        "reason": "no_gastown_installation_found",
        "message": "No existing Gastown installation detected",
    }


def create_backup(gastown_dir: Path) -> Path | None:
    """Create a backup of the Gastown configuration.

    Args:
        gastown_dir: Path to the Gastown configuration directory.

    Returns:
        Path to the backup directory, or None if backup failed.

    """
    if not gastown_dir.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = gastown_dir.parent / f"backup-gastown-{timestamp}"

    try:
        shutil.copytree(gastown_dir, backup_dir)
        logger.info("Created backup at %s", backup_dir)
        return backup_dir
    except OSError as e:
        logger.error("Failed to create backup: %s", e)
        return None


def _parse_gastown_keys(key_value: str) -> str:
    """Convert Gastown key format to gasclaw format.

    Gastown used comma-separated keys, gasclaw uses colon-separated.

    Args:
        key_value: The key string from Gastown config.

    Returns:
        Colon-separated keys for gasclaw.

    """
    # Handle both comma and colon separators
    if "," in key_value:
        keys = [k.strip() for k in key_value.split(",") if k.strip()]
        return ":".join(keys)
    return key_value.strip()


def _prompt_for_missing_config(interactive: bool = True) -> dict[str, str]:
    """Prompt user for required gasclaw configuration.

    Args:
        interactive: Whether to prompt interactively.

    Returns:
        Dict with configuration values.

    """
    config: dict[str, str] = {}

    # Always check environment variables first
    openclaw_key = os.environ.get("OPENCLAW_KIMI_KEY", "").strip()
    if openclaw_key:
        config["OPENCLAW_KIMI_KEY"] = openclaw_key

    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if telegram_token:
        config["TELEGRAM_BOT_TOKEN"] = telegram_token

    telegram_owner = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
    if telegram_owner:
        config["TELEGRAM_OWNER_ID"] = telegram_owner

    if not interactive:
        return config

    # Interactive prompts for any missing values
    print("\n📝 Additional configuration required for gasclaw:\n")

    # OPENCLAW_KIMI_KEY
    if "OPENCLAW_KIMI_KEY" not in config:
        openclaw_key = input("Enter OPENCLAW_KIMI_KEY (Kimi key for OpenClaw overseer): ").strip()
        if openclaw_key:
            config["OPENCLAW_KIMI_KEY"] = openclaw_key

    # TELEGRAM_BOT_TOKEN
    if "TELEGRAM_BOT_TOKEN" not in config:
        telegram_token = input("Enter TELEGRAM_BOT_TOKEN: ").strip()
        if telegram_token:
            config["TELEGRAM_BOT_TOKEN"] = telegram_token

    # TELEGRAM_OWNER_ID
    if "TELEGRAM_OWNER_ID" not in config:
        telegram_owner = input("Enter TELEGRAM_OWNER_ID (your Telegram user ID): ").strip()
        if telegram_owner:
            config["TELEGRAM_OWNER_ID"] = telegram_owner

    return config


def migrate_config(
    gastown_dir: Path | None = None,
    env_file: Path | None = None,
    interactive: bool = True,
) -> dict[str, Any]:
    """Migrate Gastown configuration to gasclaw format.

    Args:
        gastown_dir: Path to Gastown config directory (optional).
        env_file: Path to write gasclaw .env file (optional).
        interactive: Whether to prompt for missing config interactively.

    Returns:
        Dict with migration results.

    """
    result: dict[str, Any] = {"success": False, "migrated_keys": []}

    # Detect Gastown setup
    detection = detect_gastown_setup(gastown_dir)
    if not detection["detected"]:
        result["error"] = detection.get("message", "No Gastown installation found")
        return result

    migrated_config: dict[str, str] = {}

    # Extract configuration based on source
    if detection.get("source") == "env_var":
        kimi_key = detection.get("kimi_api_key", "")
        if kimi_key:
            migrated_config["GASTOWN_KIMI_KEYS"] = _parse_gastown_keys(kimi_key)
            result["migrated_keys"].append("KIMI_API_KEY")

    elif detection.get("source") == "config_file":
        config = detection.get("config", {})
        if "kimi_api_key" in config:
            migrated_config["GASTOWN_KIMI_KEYS"] = _parse_gastown_keys(config["kimi_api_key"])
            result["migrated_keys"].append("kimi_api_key")

    # Get additional required config
    extra_config = _prompt_for_missing_config(interactive=interactive)
    migrated_config.update(extra_config)

    # Validate we have required keys
    required = ["GASTOWN_KIMI_KEYS", "OPENCLAW_KIMI_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID"]
    missing = [k for k in required if k not in migrated_config]
    if missing:
        result["error"] = f"Missing required configuration: {', '.join(missing)}"
        return result

    # Write to env file
    if env_file:
        try:
            env_file.parent.mkdir(parents=True, exist_ok=True)
            with open(env_file, "w") as f:
                f.write("# Gasclaw configuration - migrated from Gastown\n")
                f.write(f"# Migrated on: {datetime.now().isoformat()}\n\n")

                # Required variables
                f.write("# Required: Colon-separated Kimi API keys for Gastown agents\n")
                f.write(f"GASTOWN_KIMI_KEYS={migrated_config['GASTOWN_KIMI_KEYS']}\n\n")

                f.write("# Required: Kimi API key for OpenClaw (separate pool)\n")
                f.write(f"OPENCLAW_KIMI_KEY={migrated_config['OPENCLAW_KIMI_KEY']}\n\n")

                f.write("# Required: Telegram bot token\n")
                f.write(f"TELEGRAM_BOT_TOKEN={migrated_config['TELEGRAM_BOT_TOKEN']}\n\n")

                f.write("# Required: Telegram user ID for allowlist\n")
                f.write(f"TELEGRAM_OWNER_ID={migrated_config['TELEGRAM_OWNER_ID']}\n\n")

                # Optional variables with defaults
                f.write("# Optional: Git URL or path for the rig (default: /project)\n")
                f.write("# GT_RIG_URL=/project\n\n")

                f.write("# Optional: Number of crew workers (default: 6)\n")
                f.write("# GT_AGENT_COUNT=6\n\n")

                f.write("# Optional: Health check interval in seconds (default: 300)\n")
                f.write("# MONITOR_INTERVAL=300\n\n")

                f.write("# Optional: Activity deadline in seconds (default: 3600)\n")
                f.write("# ACTIVITY_DEADLINE=3600\n\n")

                f.write("# Optional: Dolt SQL server port (default: 3307)\n")
                f.write("# DOLT_PORT=3307\n")

            result["env_file"] = str(env_file)
            result["success"] = True
            result["gastown_kimi_keys"] = migrated_config["GASTOWN_KIMI_KEYS"]
        except OSError as e:
            result["error"] = f"Failed to write env file: {e}"
            return result
    else:
        # Dry run or no env file specified
        result["success"] = True
        result["gastown_kimi_keys"] = migrated_config.get("GASTOWN_KIMI_KEYS", "")

    return result


def migrate(
    gastown_dir: Path | None = None,
    gasclaw_env_file: Path | None = None,
    dry_run: bool = False,
    interactive: bool = True,
) -> MigrationResult:
    """Migrate Gastown configuration to gasclaw.

    Detects existing Gastown installation and migrates configuration.

    Args:
        gastown_dir: Path to Gastown config directory (optional).
        gasclaw_env_file: Path to write gasclaw .env file (optional).
        dry_run: If True, only detect and report, don't modify anything.
        interactive: Whether to prompt for missing configuration.

    Returns:
        MigrationResult with details of the migration.

    """
    # Default paths
    if gasclaw_env_file is None:
        gasclaw_env_file = DEFAULT_GASCLAW_ENV

    # Detect Gastown
    detection = detect_gastown_setup(gastown_dir)

    if not detection["detected"]:
        return MigrationResult(
            success=False,
            dry_run=dry_run,
            gastown_detected=False,
            error_message=detection.get("message", "No Gastown installation found"),
        )

    if dry_run:
        return MigrationResult(
            success=True,
            dry_run=True,
            gastown_detected=True,
            migrated_keys=[],  # We don't know without doing the migration
        )

    # Create backup of gastown config if it exists
    backup_path = None
    if gastown_dir and gastown_dir.exists():
        backup_path = create_backup(gastown_dir)
    elif detection.get("source") == "config_file":
        config_dir = Path(detection.get("config_dir", ""))
        if config_dir.exists():
            backup_path = create_backup(config_dir)

    # Perform migration
    config_result = migrate_config(
        gastown_dir=gastown_dir,
        env_file=gasclaw_env_file,
        interactive=interactive,
    )

    if not config_result["success"]:
        return MigrationResult(
            success=False,
            dry_run=False,
            gastown_detected=True,
            backup_path=backup_path,
            error_message=config_result.get("error", "Unknown error during migration"),
        )

    return MigrationResult(
        success=True,
        dry_run=False,
        gastown_detected=True,
        backup_path=backup_path,
        migrated_keys=config_result.get("migrated_keys", []),
        env_file_path=gasclaw_env_file,
    )


def detect_openclaw_launcher_setup(
    openclaw_dir: Path | None = None,
    launcher_dir: Path | None = None,
) -> dict[str, Any]:
    """Detect if openclaw-launcher is installed and configured.

    Checks for:
    1. openclaw-launcher config file at ~/.openclaw/openclaw.json
    2. openclaw-launcher directory at ~/openclaw-launcher/

    Args:
        openclaw_dir: Directory containing openclaw.json (default: ~/.openclaw).
        launcher_dir: openclaw-launcher directory (default: ~/openclaw-launcher).

    Returns:
        Dict with detection results including detected status and source.
    """
    # If gasclaw config already exists, don't offer migration
    if os.environ.get("GASTOWN_KIMI_KEYS"):
        return {
            "detected": False,
            "reason": "gasclaw_config_already_exists",
            "message": "Gasclaw configuration already exists (GASTOWN_KIMI_KEYS is set)",
        }

    # Check for openclaw.json config file
    if openclaw_dir is None:
        openclaw_dir = DEFAULT_OPENCLAW_DIR

    config_file = openclaw_dir / "openclaw.json"
    if config_file.exists():
        try:
            with open(config_file) as f:
                config = json.load(f)
            return {
                "detected": True,
                "source": "config_file",
                "config_path": str(config_file),
                "config": config,
                "message": f"Found openclaw-launcher config at {config_file}",
            }
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Found openclaw.json but couldn't read it: %s", e)
            return {
                "detected": False,
                "reason": "corrupted_config",
                "message": f"Found openclaw.json but couldn't read it: {e}",
            }

    # Check for openclaw-launcher directory
    if launcher_dir is None:
        launcher_dir = DEFAULT_OPENCLAW_LAUNCHER_DIR

    if launcher_dir.exists():
        return {
            "detected": True,
            "source": "launcher_dir",
            "launcher_dir": str(launcher_dir),
            "message": f"Found openclaw-launcher directory at {launcher_dir}",
        }

    return {
        "detected": False,
        "reason": "no_openclaw_launcher_found",
        "message": "No existing openclaw-launcher installation detected",
    }


def _extract_api_keys_from_auth_profiles(openclaw_dir: Path) -> list[str]:
    """Extract API keys from agent auth-profiles.json files.

    Args:
        openclaw_dir: Path to the .openclaw directory.

    Returns:
        List of unique API keys found.
    """
    keys: list[str] = []
    agents_dir = openclaw_dir / "agents"

    if not agents_dir.exists():
        return keys

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue

        auth_file = agent_dir / "agent" / "auth-profiles.json"
        if auth_file.exists():
            try:
                with open(auth_file) as f:
                    auth_config = json.load(f)

                # Extract keys from auth profiles
                for profile_name, profile in auth_config.items():
                    if isinstance(profile, dict) and "api_key" in profile:
                        key = profile["api_key"]
                        if key and key not in keys:
                            keys.append(key)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Could not read auth-profiles.json at %s: %s", auth_file, e)

    return keys


def migrate_openclaw_launcher(
    openclaw_dir: Path | None = None,
    env_file: Path | None = None,
    interactive: bool = True,
) -> dict[str, Any]:
    """Migrate openclaw-launcher configuration to gasclaw format.

    Args:
        openclaw_dir: Path to openclaw config directory (default: ~/.openclaw).
        env_file: Path to write gasclaw .env file (optional).
        interactive: Whether to prompt for missing config interactively.

    Returns:
        Dict with migration results including warnings.
    """
    result: dict[str, Any] = {
        "success": False,
        "migrated_keys": [],
        "warnings": [],
    }

    # Detect openclaw-launcher setup
    detection = detect_openclaw_launcher_setup(openclaw_dir)
    if not detection["detected"]:
        result["error"] = detection.get("message", "No openclaw-launcher installation found")
        return result

    config = detection.get("config", {})
    migrated_config: dict[str, str] = {}
    warnings: list[str] = []

    # Extract Telegram configuration
    telegram_config = config.get("channels", {}).get("telegram", {})
    if telegram_config.get("enabled"):
        bot_token = telegram_config.get("botToken", "")
        if bot_token:
            migrated_config["TELEGRAM_BOT_TOKEN"] = bot_token
            result["migrated_keys"].append("TELEGRAM_BOT_TOKEN")

        # Handle multiple allowed user IDs
        allow_from = telegram_config.get("allowFrom", [])
        if allow_from:
            # Convert list to colon-separated string for gasclaw format
            # Issue #241 will add proper multi-user support
            migrated_config["TELEGRAM_OWNER_ID"] = ":".join(str(uid) for uid in allow_from)
            result["migrated_keys"].append("TELEGRAM_OWNER_ID")

    # Extract agent identity
    agents_list = config.get("agents", {}).get("list", [])
    if agents_list:
        first_agent = agents_list[0]
        agent_id = first_agent.get("id", "main")
        identity = first_agent.get("identity", {})

        migrated_config["AGENT_ID"] = agent_id
        result["migrated_keys"].append("AGENT_ID")

        if "name" in identity:
            migrated_config["AGENT_NAME"] = identity["name"]
            result["migrated_keys"].append("AGENT_NAME")

        if "emoji" in identity:
            migrated_config["AGENT_EMOJI"] = identity["emoji"]
            result["migrated_keys"].append("AGENT_EMOJI")

    # Handle gateway port
    gateway_config = config.get("gateway", {})
    old_port = gateway_config.get("port", 18790)
    new_port = 18789  # Gasclaw default

    migrated_config["GATEWAY_PORT"] = str(new_port)
    result["migrated_keys"].append("GATEWAY_PORT")
    result["gateway_port_old"] = old_port
    result["gateway_port_new"] = new_port

    if old_port != new_port:
        warnings.append(
            f"Gateway port changed from {old_port} to {new_port}. "
            "Make sure no other service is using port 18789."
        )

    # Extract API keys from auth-profiles
    if openclaw_dir is None:
        openclaw_dir = DEFAULT_OPENCLAW_DIR

    api_keys = _extract_api_keys_from_auth_profiles(openclaw_dir)
    if api_keys:
        # Use first key for OPENCLAW_KIMI_KEY
        migrated_config["OPENCLAW_KIMI_KEY"] = api_keys[0]
        result["migrated_keys"].append("OPENCLAW_KIMI_KEY")

        # If multiple keys, use them for GASTOWN_KIMI_KEYS too
        if len(api_keys) > 1:
            migrated_config["GASTOWN_KIMI_KEYS"] = ":".join(api_keys[1:])
            result["migrated_keys"].append("GASTOWN_KIMI_KEYS")

    # Always add warning about OPENCLAW_HOME
    warnings.append(
        "Ensure OPENCLAW_HOME environment variable is unset before starting gasclaw. "
        "This can cause conflicts with the embedded OpenClaw."
    )

    # Prompt for missing required config
    if interactive:
        print("\n📝 Additional configuration required for gasclaw:\n")

        # GASTOWN_KIMI_KEYS
        if "GASTOWN_KIMI_KEYS" not in migrated_config:
            keys_input = input(
                "Enter GASTOWN_KIMI_KEYS (colon-separated Kimi keys for agents, or press Enter to skip): "
            ).strip()
            if keys_input:
                migrated_config["GASTOWN_KIMI_KEYS"] = keys_input
                result["migrated_keys"].append("GASTOWN_KIMI_KEYS")

        # OPENCLAW_KIMI_KEY
        # GASTOWN_KIMI_KEYS
        if "GASTOWN_KIMI_KEYS" not in migrated_config:
            keys_input = input(
                "Enter GASTOWN_KIMI_KEYS (colon-separated Kimi keys for agents, or press Enter to skip): "
            ).strip()
            if keys_input:
                migrated_config["GASTOWN_KIMI_KEYS"] = keys_input
                result["migrated_keys"].append("GASTOWN_KIMI_KEYS")

        # OPENCLAW_KIMI_KEY
        if "OPENCLAW_KIMI_KEY" not in migrated_config:
            key_input = input(
                "Enter OPENCLAW_KIMI_KEY (Kimi key for OpenClaw overseer): "
            ).strip()
            if key_input:
                migrated_config["OPENCLAW_KIMI_KEY"] = key_input
                result["migrated_keys"].append("OPENCLAW_KIMI_KEY")

        # TELEGRAM_BOT_TOKEN
        if "TELEGRAM_BOT_TOKEN" not in migrated_config:
            token_input = input("Enter TELEGRAM_BOT_TOKEN: ").strip()
            if token_input:
                migrated_config["TELEGRAM_BOT_TOKEN"] = token_input
                result["migrated_keys"].append("TELEGRAM_BOT_TOKEN")

        # TELEGRAM_OWNER_ID
        if "TELEGRAM_OWNER_ID" not in migrated_config:
            owner_input = input("Enter TELEGRAM_OWNER_ID (your Telegram user ID): ").strip()
            if owner_input:
                migrated_config["TELEGRAM_OWNER_ID"] = owner_input
                result["migrated_keys"].append("TELEGRAM_OWNER_ID")

    # Validate we have required keys
    # GASTOWN_KIMI_KEYS is optional for openclaw-launcher migration (overseer focus)
    required = ["OPENCLAW_KIMI_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_OWNER_ID"]
    missing = [k for k in required if k not in migrated_config]
    if missing:
        result["error"] = f"Missing required configuration: {', '.join(missing)}"
        result["warnings"] = warnings
        return result

    # Write to env file
    if env_file:
        try:
            env_file.parent.mkdir(parents=True, exist_ok=True)
            with open(env_file, "w") as f:
                f.write("# Gasclaw configuration - migrated from openclaw-launcher\n")
                f.write(f"# Migrated on: {datetime.now().isoformat()}\n\n")

                # Required variables
                if "GASTOWN_KIMI_KEYS" in migrated_config:
                    f.write("# Required: Colon-separated Kimi API keys for Gastown agents\n")
                    f.write(f"GASTOWN_KIMI_KEYS={migrated_config['GASTOWN_KIMI_KEYS']}\n\n")

                f.write("# Required: Kimi API key for OpenClaw (separate pool)\n")
                f.write(f"OPENCLAW_KIMI_KEY={migrated_config['OPENCLAW_KIMI_KEY']}\n\n")

                f.write("# Required: Telegram bot token\n")
                f.write(f"TELEGRAM_BOT_TOKEN={migrated_config['TELEGRAM_BOT_TOKEN']}\n\n")

                f.write("# Required: Telegram user ID(s) for allowlist (colon-separated)\n")
                f.write(f"TELEGRAM_OWNER_ID={migrated_config['TELEGRAM_OWNER_ID']}\n\n")

                # Agent identity
                if "AGENT_NAME" in migrated_config:
                    f.write("# Optional: Agent name\n")
                    f.write(f"AGENT_NAME={migrated_config['AGENT_NAME']}\n\n")

                if "AGENT_EMOJI" in migrated_config:
                    f.write("# Optional: Agent emoji\n")
                    f.write(f"AGENT_EMOJI={migrated_config['AGENT_EMOJI']}\n\n")

                # Gateway port
                f.write("# Optional: Gateway port (default: 18789)\n")
                f.write(f"GATEWAY_PORT={migrated_config.get('GATEWAY_PORT', '18789')}\n\n")

                # Optional variables with defaults
                f.write("# Optional: Git URL or path for the rig (default: /project)\n")
                f.write("# GT_RIG_URL=/project\n\n")

                f.write("# Optional: Number of crew workers (default: 6)\n")
                f.write("# GT_AGENT_COUNT=6\n\n")

                f.write("# Optional: Health check interval in seconds (default: 300)\n")
                f.write("# MONITOR_INTERVAL=300\n\n")

                f.write("# Optional: Activity deadline in seconds (default: 3600)\n")
                f.write("# ACTIVITY_DEADLINE=3600\n\n")

                f.write("# Optional: Dolt SQL server port (default: 3307)\n")
                f.write("# DOLT_PORT=3307\n")

            result["env_file"] = str(env_file)
            result["success"] = True
        except OSError as e:
            result["error"] = f"Failed to write env file: {e}"
            result["warnings"] = warnings
            return result
    else:
        # Dry run mode
        result["success"] = True

    result["warnings"] = warnings
    return result
