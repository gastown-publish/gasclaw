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

    def test_skips_non_skill_files_in_source(self, tmp_path):
        """Non-directory items in source (like README.md) are skipped."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"
        self._make_source_skills(src)
        # Create a file in the source that should be ignored
        (src / "README.md").write_text("# Skills")
        (src / ".DS_Store").write_text("")
        install_skills(skills_src=src, skills_dst=dst)
        # Only the skill directory should be copied
        assert (dst / "gastown-health").exists()
        assert not (dst / "README.md").exists()
        assert not (dst / ".DS_Store").exists()

    def test_handles_nested_directories(self, tmp_path):
        """Skill directories with nested subdirectories are copied."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"

        # Create skill with nested directory
        skill_dir = src / "complex-skill"
        nested_dir = skill_dir / "data" / "templates"
        nested_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Complex Skill")
        (nested_dir / "template.j2").write_text("template content")

        install_skills(skills_src=src, skills_dst=dst)

        assert (dst / "complex-skill" / "data" / "templates" / "template.j2").exists()
        assert (dst / "complex-skill" / "data" / "templates" / "template.j2").read_text() == "template content"

    def test_overwrites_existing_skills(self, tmp_path):
        """Installing over existing skills replaces them."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"
        self._make_source_skills(src)

        # Pre-create an old version of the skill
        old_skill = dst / "gastown-health"
        old_skill.mkdir(parents=True)
        (old_skill / "SKILL.md").write_text("# Old Version")
        (old_skill / "old-file.txt").write_text("should be removed")

        install_skills(skills_src=src, skills_dst=dst)

        # Should have new content, not old
        assert "# Health Skill" in (dst / "gastown-health" / "SKILL.md").read_text()
        assert not (dst / "gastown-health" / "old-file.txt").exists()

    def test_empty_source_directory(self, tmp_path):
        """Empty source directory results in no skills copied."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"
        src.mkdir()
        install_skills(skills_src=src, skills_dst=dst)
        assert dst.exists()
        assert len(list(dst.iterdir())) == 0

    def test_skill_without_scripts_dir(self, tmp_path):
        """Skills without scripts directory don't cause errors."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"

        # Create skill without scripts
        skill_dir = src / "minimal-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Minimal Skill")

        install_skills(skills_src=src, skills_dst=dst)

        assert (dst / "minimal-skill" / "SKILL.md").exists()
        assert not (dst / "minimal-skill" / "scripts").exists()

    def test_multiple_skills(self, tmp_path):
        """Multiple skills are copied correctly."""
        src = tmp_path / "src-skills"
        dst = tmp_path / "dst-skills"

        for name in ["skill-a", "skill-b", "skill-c"]:
            skill_dir = src / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# {name}")

        install_skills(skills_src=src, skills_dst=dst)

        for name in ["skill-a", "skill-b", "skill-c"]:
            assert (dst / name / "SKILL.md").exists()
            assert f"# {name}" in (dst / name / "SKILL.md").read_text()
