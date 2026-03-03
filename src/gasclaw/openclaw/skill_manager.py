"""Copy gasclaw skills to the OpenClaw skills directory."""

from __future__ import annotations

import logging
import shutil
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

__all__ = ["install_skills"]


def install_skills(
    *,
    skills_src: Path,
    skills_dst: Path,
) -> None:
    """Copy skills from source to OpenClaw skills directory.

    Args:
        skills_src: Source directory containing skill folders.
        skills_dst: Destination directory (e.g. ~/.openclaw/skills/).

    Raises:
        PermissionError: If unable to create destination or make scripts executable.
        OSError: If unable to copy skill files.

    """
    try:
        skills_dst.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured skills destination exists: %s", skills_dst)
    except PermissionError:
        logger.error("Permission denied creating skills directory: %s", skills_dst)
        raise

    for skill_dir in skills_src.iterdir():
        if not skill_dir.is_dir():
            logger.debug("Skipping non-directory item: %s", skill_dir.name)
            continue

        dst_skill = skills_dst / skill_dir.name
        try:
            if dst_skill.exists():
                logger.debug("Removing existing skill: %s", dst_skill.name)
                shutil.rmtree(dst_skill)
            shutil.copytree(skill_dir, dst_skill)
            logger.info("Installed skill: %s", skill_dir.name)
        except PermissionError as e:
            logger.error("Permission denied installing skill %s: %s", skill_dir.name, e)
            raise
        except OSError as e:
            logger.error("Error copying skill %s: %s", skill_dir.name, e)
            raise

        # Make all .sh scripts executable
        scripts_dir = dst_skill / "scripts"
        if scripts_dir.is_dir():
            for script in scripts_dir.glob("*.sh"):
                try:
                    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
                    logger.debug("Made script executable: %s", script.name)
                except PermissionError as e:
                    logger.error(
                        "Permission denied making script executable %s: %s", script.name, e
                    )
                    raise
