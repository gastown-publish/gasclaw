"""Copy gasclaw skills to the OpenClaw skills directory."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

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
    """
    skills_dst.mkdir(parents=True, exist_ok=True)

    for skill_dir in skills_src.iterdir():
        if not skill_dir.is_dir():
            continue

        dst_skill = skills_dst / skill_dir.name
        if dst_skill.exists():
            shutil.rmtree(dst_skill)
        shutil.copytree(skill_dir, dst_skill)

        # Make all .sh scripts executable
        scripts_dir = dst_skill / "scripts"
        if scripts_dir.is_dir():
            for script in scripts_dir.glob("*.sh"):
                script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
