"""Tests for gasclaw.openclaw.skill_manager."""

from __future__ import annotations

import os

from gasclaw.openclaw.skill_manager import install_skills


class TestInstallSkills:
    def _make_source_skills(self, src_dir):
        """Create a minimal skills source directory."""
        skill_dir = src_dir / "gastown-health"
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Health Skill")
        (scripts_dir / "gt-status.sh").write_text("#!/bin/bash\necho ok")

    def test_copies_skills_to_destination(self, tmp_path):
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"
        self._make_source_skills(src)
        install_skills(skills_src=src, skills_dst=dst)
        assert (dst / "gastown-health" / "SKILL.md").exists()
        assert (dst / "gastown-health" / "scripts" / "gt-status.sh").exists()

    def test_scripts_are_executable(self, tmp_path):
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"
        self._make_source_skills(src)
        install_skills(skills_src=src, skills_dst=dst)
        script = dst / "gastown-health" / "scripts" / "gt-status.sh"
        assert os.access(script, os.X_OK)

    def test_idempotent(self, tmp_path):
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"
        self._make_source_skills(src)
        install_skills(skills_src=src, skills_dst=dst)
        install_skills(skills_src=src, skills_dst=dst)
        assert (dst / "gastown-health" / "SKILL.md").exists()

    def test_creates_destination_dir(self, tmp_path):
        src = tmp_path / "src-skills"
        dst = tmp_path / "nonexistent" / "skills"
        self._make_source_skills(src)
        install_skills(skills_src=src, skills_dst=dst)
        assert dst.is_dir()
