"""Tests for gasclaw.migration module."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from gasclaw.migration import (
    MigrationResult,
    create_backup,
    detect_gastown_setup,
    migrate,
    migrate_config,
)


class TestDetectGastownSetup:
    """Tests for detect_gastown_setup function."""

    def test_detects_gastown_env_var(self, monkeypatch):
        """Detects Gastown via KIMI_API_KEY environment variable."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-kimi123")
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        result = detect_gastown_setup()

        assert result["detected"] is True
        assert result["source"] == "env_var"
        assert result["kimi_api_key"] == "sk-kimi123"

    def test_detects_no_gastown_when_gasclaw_config_exists(self, monkeypatch):
        """Returns not detected when gasclaw config already exists."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-kimi123")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-key1:sk-key2")

        result = detect_gastown_setup()

        assert result["detected"] is False
        assert result["reason"] == "gasclaw_config_already_exists"

    def test_detects_no_gastown_when_no_env_var(self, monkeypatch):
        """Returns not detected when no Gastown env var found."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        result = detect_gastown_setup()

        assert result["detected"] is False
        assert result["reason"] == "no_gastown_installation_found"

    def test_detects_gastown_config_file(self, tmp_path, monkeypatch):
        """Detects Gastown via config file."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        # Create mock gastown config
        gt_config = tmp_path / ".gt" / "config.json"
        gt_config.parent.mkdir(parents=True)
        gt_config.write_text(json.dumps({"kimi_api_key": "sk-from-file"}))

        result = detect_gastown_setup([gt_config.parent])

        assert result["detected"] is True
        assert result["source"] == "config_file"

    def test_handles_corrupted_config_file(self, tmp_path, monkeypatch):
        """Skips corrupted config files and continues searching."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        # Create corrupted config
        gt_config = tmp_path / ".gt" / "config.json"
        gt_config.parent.mkdir(parents=True)
        gt_config.write_text("not valid json {{{")

        result = detect_gastown_setup([gt_config.parent])

        # Should not crash, just not detect
        assert result["detected"] is False

    def test_handles_config_file_permission_error(self, tmp_path, monkeypatch):
        """Handles permission errors when reading config file."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        # Create config file
        gt_config = tmp_path / ".gt" / "config.json"
        gt_config.parent.mkdir(parents=True)
        gt_config.write_text(json.dumps({"kimi_api_key": "sk-from-file"}))

        # Remove read permissions
        gt_config.chmod(0o000)

        try:
            result = detect_gastown_setup([gt_config.parent])
            # Should not crash, just not detect
            assert result["detected"] is False
        finally:
            # Restore permissions for cleanup
            gt_config.chmod(0o644)


class TestMigrateConfig:
    """Tests for migrate_config function."""

    def test_migrates_kimi_api_key_to_gastown_keys(self, tmp_path, monkeypatch):
        """Migrates single KIMI_API_KEY to GASTOWN_KIMI_KEYS format."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("KIMI_API_KEY", "sk-migrate-key")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-oc")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")

        env_file = tmp_path / ".env"

        result = migrate_config(env_file=env_file, interactive=False)

        assert result["success"] is True
        assert result["gastown_kimi_keys"] == "sk-migrate-key"
        assert "KIMI_API_KEY" in result["migrated_keys"]

    def test_migrates_multiple_keys(self, tmp_path, monkeypatch):
        """Handles multiple keys in KIMI_API_KEY."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("KIMI_API_KEY", "sk-key1,sk-key2,sk-key3")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-oc")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")

        env_file = tmp_path / ".env"

        result = migrate_config(env_file=env_file, interactive=False)

        assert result["success"] is True
        assert result["gastown_kimi_keys"] == "sk-key1:sk-key2:sk-key3"

    def test_reads_from_gastown_config_file(self, tmp_path, monkeypatch):
        """Reads configuration from Gastown config file."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-oc")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")

        gt_dir = tmp_path / ".gt"
        gt_dir.mkdir()
        config_file = gt_dir / "config.json"
        config_file.write_text(json.dumps({
            "kimi_api_key": "sk-from-config",
        }))

        result = migrate_config(gastown_dir=gt_dir, interactive=False)

        assert result["success"] is True
        assert result["gastown_kimi_keys"] == "sk-from-config"

    def test_handles_missing_config_gracefully(self, tmp_path, monkeypatch):
        """Returns error when no configuration can be found."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        env_file = tmp_path / ".env"

        result = migrate_config(env_file=env_file, interactive=False)

        assert result["success"] is False
        assert "error" in result

    def test_returns_error_when_missing_required_config(self, tmp_path, monkeypatch):
        """Returns error when required configuration is missing."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("KIMI_API_KEY", "sk-migrate-key")
        # Don't set other required env vars
        monkeypatch.delenv("OPENCLAW_KIMI_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_OWNER_ID", raising=False)

        env_file = tmp_path / ".env"

        result = migrate_config(env_file=env_file, interactive=False)

        assert result["success"] is False
        assert "Missing required configuration" in result["error"]

    def test_handles_env_file_write_error(self, tmp_path, monkeypatch):
        """Handles OSError when writing env file."""
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("KIMI_API_KEY", "sk-migrate-key")
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-oc")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")

        # Use a directory path as env_file to trigger OSError on write
        env_file = tmp_path / "is_a_directory"
        env_file.mkdir()

        result = migrate_config(env_file=env_file, interactive=False)

        assert result["success"] is False
        assert "Failed to write env file" in result["error"]


class TestCreateBackup:
    """Tests for create_backup function."""

    def test_creates_backup_directory(self, tmp_path):
        """Creates backup directory with timestamp."""
        gastown_dir = tmp_path / ".gt"
        gastown_dir.mkdir()
        config_file = gastown_dir / "config.json"
        config_file.write_text('{"key": "value"}')

        backup_dir = create_backup(gastown_dir)

        assert backup_dir.exists()
        assert backup_dir.name.startswith("backup-")
        assert (backup_dir / "config.json").exists()

    def test_handles_nonexistent_gastown_dir(self, tmp_path):
        """Returns None when gastown directory doesn't exist."""
        backup_dir = create_backup(tmp_path / "nonexistent")

        assert backup_dir is None

    def test_handles_backup_copy_error(self, tmp_path, monkeypatch):
        """Returns None when backup copy fails."""
        gastown_dir = tmp_path / ".gt"
        gastown_dir.mkdir()
        config_file = gastown_dir / "config.json"
        config_file.write_text('{"key": "value"}')

        # Mock shutil.copytree to raise OSError
        def mock_copytree(*args, **kwargs):
            raise OSError("Permission denied")

        monkeypatch.setattr("gasclaw.migration.shutil.copytree", mock_copytree)

        backup_dir = create_backup(gastown_dir)

        assert backup_dir is None


class TestMigrate:
    """Tests for main migrate function."""

    def test_successful_migration(self, tmp_path, monkeypatch):
        """Full migration succeeds when setup detected."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-migrate")
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-oc")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")

        result = migrate(
            gastown_dir=tmp_path / ".gt",
            gasclaw_env_file=tmp_path / ".env",
            dry_run=False,
            interactive=False,
        )

        assert isinstance(result, MigrationResult)
        assert result.success is True
        assert result.migrated_keys == ["KIMI_API_KEY"]

    def test_dry_run_does_not_modify_files(self, tmp_path, monkeypatch):
        """Dry run performs detection without file modifications."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-dryrun")
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)

        env_file = tmp_path / ".env"

        result = migrate(
            gastown_dir=tmp_path / ".gt",
            gasclaw_env_file=env_file,
            dry_run=True,
        )

        assert result.success is True
        assert result.dry_run is True
        assert not env_file.exists()

    def test_migration_fails_when_gasclaw_already_configured(self, tmp_path, monkeypatch):
        """Migration fails if gasclaw config already exists."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-test")
        monkeypatch.setenv("GASTOWN_KIMI_KEYS", "sk-already-set")

        result = migrate(interactive=False)

        assert result.success is False
        assert "gasclaw configuration already exists" in result.error_message.lower()

    def test_migration_creates_env_file(self, tmp_path, monkeypatch):
        """Migration creates .env file with migrated config."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-env-key")
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-oc")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")

        env_file = tmp_path / ".env"

        result = migrate(
            gasclaw_env_file=env_file,
            dry_run=False,
            interactive=False,
        )

        assert result.success is True
        assert env_file.exists()
        content = env_file.read_text()
        assert "GASTOWN_KIMI_KEYS=sk-env-key" in content

    def test_migration_preserves_openclaw_key(self, tmp_path, monkeypatch):
        """Migration prompts for OPENCLAW_KIMI_KEY if not set."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-gastown")
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.delenv("OPENCLAW_KIMI_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_OWNER_ID", raising=False)

        env_file = tmp_path / ".env"

        # Mock interactive input
        with patch("builtins.input", side_effect=["sk-openclaw", "123:TOKEN", "123456"]):
            result = migrate(
                gasclaw_env_file=env_file,
                dry_run=False,
            )

        assert result.success is True
        content = env_file.read_text()
        assert "OPENCLAW_KIMI_KEY=sk-openclaw" in content

    def test_creates_backup_when_config_file_source(self, tmp_path, monkeypatch):
        """Creates backup when gastown detected via config_file source."""
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        monkeypatch.setenv("OPENCLAW_KIMI_KEY", "sk-oc")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_OWNER_ID", "123456")

        # Create gastown config directory at the exact path
        gt_dir = tmp_path / ".gt"
        gt_dir.mkdir()
        config_file = gt_dir / "config.json"
        config_file.write_text(json.dumps({"kimi_api_key": "sk-from-config"}))

        env_file = tmp_path / ".env"

        # Pass the gastown directory - this covers the backup path
        result = migrate(
            gastown_dir=gt_dir,
            gasclaw_env_file=env_file,
            dry_run=False,
            interactive=False,
        )

        assert result.success is True
        assert result.backup_path is not None

    def test_migration_fails_when_config_migration_fails(self, tmp_path, monkeypatch):
        """Migration returns failure when migrate_config fails."""
        monkeypatch.setenv("KIMI_API_KEY", "sk-migrate")
        monkeypatch.delenv("GASTOWN_KIMI_KEYS", raising=False)
        # Don't set required env vars to trigger failure
        monkeypatch.delenv("OPENCLAW_KIMI_KEY", raising=False)
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_OWNER_ID", raising=False)

        env_file = tmp_path / ".env"

        result = migrate(
            gasclaw_env_file=env_file,
            dry_run=False,
            interactive=False,
        )

        assert result.success is False
        assert "Missing required configuration" in result.error_message


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_summary_format(self):
        """Summary returns formatted string with migration details."""
        result = MigrationResult(
            success=True,
            dry_run=False,
            gastown_detected=True,
            backup_path=Path("/tmp/backup-123"),
            migrated_keys=["KIMI_API_KEY", "TELEGRAM_BOT_TOKEN"],
            env_file_path=Path("/workspace/.env"),
        )

        summary = result.summary()

        assert "Migration successful" in summary
        assert "KIMI_API_KEY" in summary
        assert "/workspace/.env" in summary

    def test_summary_with_error(self):
        """Summary includes error message on failure."""
        result = MigrationResult(
            success=False,
            dry_run=False,
            gastown_detected=False,
            error_message="No gastown installation found",
        )

        summary = result.summary()

        assert "Migration failed" in summary
        assert "No gastown installation found" in summary

    def test_summary_shows_dry_run(self):
        """Summary indicates when run was a dry run."""
        result = MigrationResult(
            success=True,
            dry_run=True,
            gastown_detected=True,
            migrated_keys=["KIMI_API_KEY"],
        )

        summary = result.summary()

        assert "DRY RUN" in summary
