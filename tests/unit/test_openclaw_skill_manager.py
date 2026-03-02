"""Tests for gasclaw.openclaw.skill_manager."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

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

class TestInstallSkillsErrorHandling:
    """Tests for error handling in install_skills."""

    def test_handles_permission_error_on_destination(self, tmp_path, monkeypatch):
        """PermissionError when creating destination is raised."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"

        # Create source skill
        skill_dir = src / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Test")

        # Mock mkdir to raise PermissionError
        def mock_mkdir(*args, **kwargs):
            raise PermissionError("Permission denied")

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        with pytest.raises(PermissionError):
            install_skills(skills_src=src, skills_dst=dst)

    def test_handles_os_error_on_copy(self, tmp_path, monkeypatch):
        """OSError when copying skill is raised."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"

        # Create source skill
        skill_dir = src / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Test")

        # Mock copytree to raise OSError
        import shutil
        def mock_copytree(*args, **kwargs):
            raise OSError("Disk full")

        monkeypatch.setattr(shutil, "copytree", mock_copytree)

        with pytest.raises(OSError):
            install_skills(skills_src=src, skills_dst=dst)
