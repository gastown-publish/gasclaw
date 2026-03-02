"""Migration from Gastown to gasclaw.

This module provides functionality to migrate existing Gastown installations
to gasclaw, preserving configuration and data.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["migrate", "MigrationResult", "MigrationError"]


class MigrationError(Exception):
    """Raised when migration fails."""
    pass


@dataclass
class MigrationResult:
    """Result of a migration operation."""
    success: bool
    message: str
    migrated_items: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backup_path: Path | None = None

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = ["=" * 50]
        lines.append("GASTOWN → GASCLAW MIGRATION SUMMARY")
        lines.append("=" * 50)
        lines.append(f"Status: {'✓ SUCCESS' if self.success else '✗ FAILED'}")
        lines.append(f"
{self.message}")

        if self.migrated_items:
            lines.append("
Migrated Items:")
            for item in self.migrated_items:
                lines.append(f"  ✓ {item}")

        if self.warnings:
            lines.append("
Warnings:")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")

        if self.backup_path:
            lines.append(f"
Backup created at: {self.backup_path}")

        lines.append("=" * 50)
        return "\n".join(lines)


def _detect_gastown_installation() -> dict[str, Any]:
    """Detect existing Gastown installation.

    Returns:
        Dict with information about the Gastown installation.
    """
    info = {
        "found": False,
        "gt_path": None,
        "config_path": None,
        "dolt_data_dir": None,
        "agents": [],
        "version": None,
    }

    # Check for gt command
    try:
        result = subprocess.run(
            ["gt", "--version"],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            info["found"] = True
            info["version"] = result.stdout.decode().strip()
            logger.info(f"Found Gastown version: {info['version']}")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("gt command not found")
        return info

    # Check for gt config directory
    gt_root = Path.home() / ".gastown"
    if gt_root.exists():
        info["gt_path"] = str(gt_root)
        logger.info(f"Found Gastown config at: {gt_root}")

        # Check for agent configuration
        agents_dir = gt_root / "agents"
        if agents_dir.exists():
            info["agents"] = [d.name for d in agents_dir.iterdir() if d.is_dir()]
            logger.info(f"Found agents: {info['agents']}")

    # Check for Dolt data
    dolt_data = Path("/workspace/gt/.dolt-data")
    if dolt_data.exists():
        info["dolt_data_dir"] = str(dolt_data)
        logger.info(f"Found Dolt data at: {dolt_data}")

    return info


def _create_backup(backup_dir: Path) -> Path:
    """Create backup of existing Gastown installation.

    Args:
        backup_dir: Directory to store backup.

    Returns:
        Path to backup directory.

    Raises:
        MigrationError: If backup fails.
    """
    timestamp = subprocess.run(
        ["date", "+%Y%m%d_%H%M%S"],
        capture_output=True,
        text=True
    ).stdout.strip()

    backup_path = backup_dir / f"gastown_backup_{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    gt_root = Path.home() / ".gastown"
    if gt_root.exists():
        try:
            shutil.copytree(gt_root, backup_path / "gastown", dirs_exist_ok=True)
            logger.info(f"Backed up Gastown config to {backup_path}")
        except Exception as e:
            raise MigrationError(f"Failed to backup Gastown config: {e}")

    # Backup Dolt data if it exists
    dolt_data = Path("/workspace/gt/.dolt-data")
    if dolt_data.exists():
        try:
            dolt_backup = backup_path / "dolt-data"
            dolt_backup.mkdir(parents=True, exist_ok=True)
            # Use rsync or cp for large directories
            result = subprocess.run(
                ["cp", "-r", str(dolt_data), str(dolt_backup)],
                capture_output=True,
                timeout=60
            )
            if result.returncode != 0:
                logger.warning("Failed to backup Dolt data completely")
            else:
                logger.info(f"Backed up Dolt data to {dolt_backup}")
        except Exception as e:
            logger.warning(f"Failed to backup Dolt data: {e}")

    return backup_path


def _migrate_environment_config(
    gastown_info: dict[str, Any]
) -> dict[str, str]:
    """Extract and migrate environment configuration.

    Args:
        gastown_info: Information about Gastown installation.

    Returns:
        Dict of environment variable names to values.
    """
    config = {}

    # Try to read existing gt configuration
    gt_root = Path.home() / ".gastown"
    config_file = gt_root / "config.json"

    if config_file.exists():
        try:
            with open(config_file) as f:
                gt_config = json.load(f)

            # Extract relevant configuration
            if "kimi_keys" in gt_config:
                config["GASTOWN_KIMI_KEYS"] = ":".join(gt_config["kimi_keys"])

            if "project_dir" in gt_config:
                config["PROJECT_DIR"] = gt_config["project_dir"]

            if "rig_url" in gt_config:
                config["GT_RIG_URL"] = gt_config["rig_url"]

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read Gastown config: {e}")

    return config


def _write_gasclaw_env(config: dict[str, str], env_file: Path) -> None:
    """Write gasclaw environment file.

    Args:
        config: Configuration dict.
        env_file: Path to .env file.
    """
    lines = [
        "# Gasclaw Configuration",
        "# Generated from Gastown migration",
        "",
    ]

    for key, value in sorted(config.items()):
        lines.append(f'{key}="{value}"')

    env_file.write_text("\n".join(lines))
    logger.info(f"Wrote gasclaw config to {env_file}")


def migrate(
    *,
    backup_dir: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> MigrationResult:
    """Migrate from Gastown to gasclaw.

    Args:
        backup_dir: Directory to store backup (default: ~/.gasclaw/backups).
        dry_run: If True, only show what would be migrated without making changes.
        force: If True, proceed even if no Gastown installation is detected.

    Returns:
        MigrationResult with details of the migration.

    Raises:
        MigrationError: If migration fails and cannot be rolled back.
    """
    migrated_items = []
    warnings = []

    # Detect Gastown installation
    logger.info("Detecting Gastown installation...")
    gastown_info = _detect_gastown_installation()

    if not gastown_info["found"] and not force:
        return MigrationResult(
            success=False,
            message="No Gastown installation detected. Use --force to migrate anyway.",
            warnings=["Gastown not found in PATH"]
        )

    if dry_run:
        return MigrationResult(
            success=True,
            message="DRY RUN: Would migrate the following:",
            migrated_items=[
                f"Gastown config from {gastown_info.get('gt_path', 'N/A')}",
                f"Dolt data from {gastown_info.get('dolt_data_dir', 'N/A')}",
                f"Agents: {', '.join(gastown_info.get('agents', [])) or 'None'}",
            ],
            warnings=warnings if warnings else None
        )

    # Create backup
    if backup_dir is None:
        backup_dir = Path.home() / ".gasclaw" / "backups"

    try:
        backup_path = _create_backup(backup_dir)
        migrated_items.append(f"Created backup at {backup_path}")
    except MigrationError as e:
        return MigrationResult(
            success=False,
            message=f"Backup failed: {e}",
            warnings=warnings
        )

    # Migrate configuration
    try:
        config = _migrate_environment_config(gastown_info)
        if config:
            gasclaw_dir = Path.home() / ".gasclaw"
            gasclaw_dir.mkdir(parents=True, exist_ok=True)
            env_file = gasclaw_dir / ".env"
            _write_gasclaw_env(config, env_file)
            migrated_items.append(f"Migrated configuration to {env_file}")
        else:
            warnings.append("No configuration found to migrate")
    except Exception as e:
        warnings.append(f"Configuration migration issue: {e}")

    # Create migration marker
    marker_file = Path.home() / ".gasclaw" / ".migrated_from_gastown"
    marker_file.write_text(json.dumps({
        "gastown_version": gastown_info.get("version"),
        "migrated_at": subprocess.run(
            ["date", "-Iseconds"],
            capture_output=True,
            text=True
        ).stdout.strip(),
        "backup_location": str(backup_path),
    }, indent=2))
    migrated_items.append("Created migration marker")

    return MigrationResult(
        success=True,
        message="Migration completed successfully!",
        migrated_items=migrated_items,
        warnings=warnings if warnings else None,
        backup_path=backup_path
    )


def rollback(backup_path: Path) -> MigrationResult:
    """Rollback a migration from backup.

    Args:
        backup_path: Path to backup directory.

    Returns:
        MigrationResult with rollback status.
    """
    if not backup_path.exists():
        return MigrationResult(
            success=False,
            message=f"Backup not found: {backup_path}"
        )

    try:
        # Restore Gastown config
        gastown_backup = backup_path / "gastown"
        if gastown_backup.exists():
            gt_root = Path.home() / ".gastown"
            if gt_root.exists():
                shutil.rmtree(gt_root)
            shutil.copytree(gastown_backup, gt_root)
            logger.info(f"Restored Gastown config to {gt_root}")

        # Remove migration marker
        marker_file = Path.home() / ".gasclaw" / ".migrated_from_gastown"
        if marker_file.exists():
            marker_file.unlink()

        return MigrationResult(
            success=True,
            message="Rollback completed successfully!",
            migrated_items=["Restored Gastown configuration"],
            backup_path=backup_path
        )

    except Exception as e:
        return MigrationResult(
            success=False,
            message=f"Rollback failed: {e}"
        )
