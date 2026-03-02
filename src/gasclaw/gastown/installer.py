"""Gastown installation: kimi accounts and gt setup."""

from __future__ import annotations

import subprocess
from pathlib import Path

import tomlkit

__all__ = ["gastown_install", "setup_kimi_accounts"]


def _write_kimi_config(account_dir: Path, api_key: str) -> None:
    """Write a single kimi account config.toml."""
    account_dir.mkdir(parents=True, exist_ok=True)

    doc = tomlkit.document()
    doc.add("default_model", "kimi-code/kimi-for-coding")
    doc.add("default_thinking", True)
    doc.add("default_yolo", False)

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
        keys: List of Kimi API keys.
        accounts_dir: Override for ~/.kimi-accounts.
    """
    if accounts_dir is None:
        accounts_dir = Path.home() / ".kimi-accounts"

    for i, key in enumerate(keys, start=1):
        _write_kimi_config(accounts_dir / str(i), key)


def gastown_install(*, gt_root: Path, rig_url: str) -> None:
    """Run gt install and gt rig add.

    Args:
        gt_root: Where to install Gastown (e.g. /workspace/gt).
        rig_url: Git URL or path for the rig.
    """
    subprocess.run(
        ["gt", "install", str(gt_root), "--git"],
        check=True,
    )
    subprocess.run(
        ["gt", "rig", "add", "project", rig_url],
        check=True,
    )
