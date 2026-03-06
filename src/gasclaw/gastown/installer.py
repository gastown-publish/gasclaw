"""Gastown installation: kimi accounts, git identity, and gt setup."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import tomlkit

logger = logging.getLogger(__name__)

__all__ = ["gastown_install", "setup_kimi_accounts", "setup_git_identity"]


def _write_kimi_config(account_dir: Path, api_key: str) -> None:
    """Write a single kimi account config.toml."""
    account_dir.mkdir(parents=True, exist_ok=True)

    doc = tomlkit.document()
    doc.add("default_model", "kimi-code/kimi-for-coding")  # type: ignore[arg-type]
    doc.add("default_thinking", True)  # type: ignore[arg-type]
    doc.add("default_yolo", False)  # type: ignore[arg-type]

    # Model definition
    models = tomlkit.table(is_super_table=True)
    model_cfg = tomlkit.table()
    model_cfg.add("provider", "kimi-api")
    model_cfg.add("model", "kimi-for-coding")
    model_cfg.add("max_context_size", 262144)
    model_cfg.add("capabilities", ["thinking", "image_in", "video_in"])
    models.add("kimi-code/kimi-for-coding", model_cfg)
    doc.add("models", models)

    # Provider
    providers = tomlkit.table(is_super_table=True)
    provider = tomlkit.table()
    provider.add("type", "kimi")
    provider.add("base_url", "https://api.kimi.com/coding/v1")
    provider.add("api_key", api_key)
    providers.add("kimi-api", provider)
    doc.add("providers", providers)

    (account_dir / "config.toml").write_text(tomlkit.dumps(doc))


def setup_kimi_accounts(
    keys: list[str],
    *,
    accounts_dir: Path | None = None,
) -> None:
    """Write ~/.kimi-accounts/<N>/config.toml for each key.

    Args:
        keys: list of Kimi API keys.
        accounts_dir: Override for ~/.kimi-accounts.

    """
    if accounts_dir is None:
        accounts_dir = Path.home() / ".kimi-accounts"

    for i, key in enumerate(keys, start=1):
        _write_kimi_config(accounts_dir / str(i), key)


def setup_git_identity() -> None:
    """Configure git and dolt identity (required for gt install).
    
    Sets user.name and user.email for both git and dolt if not already configured.
    Uses default values suitable for containerized deployments.
    
    Raises:
        subprocess.CalledProcessError: If git/dolt commands fail.
    """
    # Default identity for containerized deployments
    default_name = "Gasclaw Agent"
    default_email = "agent@gasclaw.local"
    
    # Configure git identity
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.name"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            subprocess.run(
                ["git", "config", "--global", "user.name", default_name],
                check=True,
            )
            logger.info("Set git user.name to '%s'", default_name)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to configure git user.name: {e}") from e
    
    try:
        result = subprocess.run(
            ["git", "config", "--global", "user.email"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not result.stdout.strip():
            subprocess.run(
                ["git", "config", "--global", "user.email", default_email],
                check=True,
            )
            logger.info("Set git user.email to '%s'", default_email)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to configure git user.email: {e}") from e
    
    # Configure dolt identity (uses git config, but ensure it's set)
    try:
        subprocess.run(
            ["dolt", "config", "--global", "--add", "user.name", default_name],
            check=False,  # May already be set, don't fail
        )
        subprocess.run(
            ["dolt", "config", "--global", "--add", "user.email", default_email],
            check=False,  # May already be set, don't fail
        )
    except FileNotFoundError:
        # dolt not installed yet, will be checked later
        pass


def gastown_install(*, gt_root: Path, rig_url: str) -> None:
    """Run gt install, gt dolt init-rig, and gt rig add.

    Args:
        gt_root: Where to install Gastown (e.g. /workspace/gt).
        rig_url: Git URL or path for the rig.

    """
    # Run gt install
    subprocess.run(
        ["gt", "install", str(gt_root), "--git"],
        check=True,
    )
    
    # Initialize Dolt rig (creates the database) (#312)
    subprocess.run(
        ["gt", "dolt", "init-rig"],
        check=True,
        cwd=str(gt_root),
    )
    
    # Add rig with --adopt --url flags (#313)
    subprocess.run(
        ["gt", "rig", "add", "project", "--adopt", "--url", rig_url],
        check=True,
        cwd=str(gt_root),
    )
