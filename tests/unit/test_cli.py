"""Tests for gasclaw.cli."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gasclaw.cli import app
from gasclaw.config import GasclawConfig

runner = CliRunner()


@pytest.fixture
def config():
    return GasclawConfig(
        gastown_kimi_keys=["sk-key1", "sk-key2"],
        openclaw_kimi_key="sk-oc",
        telegram_bot_token="123:ABC",
        telegram_owner_id="999",
    )


class TestStartCommand:
    def test_exits_on_config_error(self):
        """start command exits with code 1 if config is invalid."""
        with patch("gasclaw.cli.load_config", side_effect=ValueError("missing env")):
            result = runner.invoke(app, ["start"])
            assert result.exit_code == 1
            assert "Config error" in result.output

    def test_calls_bootstrap_and_monitor_loop(self, config, monkeypatch, tmp_path):
        """start command bootstraps and enters monitor loop."""
        bootstrap_calls = []
        monitor_calls = []

        def mock_bootstrap(cfg, gt_root):
            bootstrap_calls.append((cfg, gt_root))

        def mock_monitor(cfg):
            monitor_calls.append(cfg)
            raise KeyboardInterrupt  # Exit after one iteration

        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", mock_bootstrap)
        monkeypatch.setattr("gasclaw.cli.monitor_loop", mock_monitor)

        result = runner.invoke(app, ["start", "--gt-root", str(tmp_path)])

        assert len(bootstrap_calls) == 1
        assert bootstrap_calls[0][1] == tmp_path
        assert len(monitor_calls) == 1
        assert "Starting gasclaw" in result.output

    def test_start_with_project_dir_override(self, config, monkeypatch, tmp_path):
        """start command overrides project_dir when provided via --project-dir."""
        monitor_calls = []
        project_override = tmp_path / "custom_project"
        project_override.mkdir()

        def mock_bootstrap(cfg, gt_root):
            pass

        def mock_monitor(cfg):
            monitor_calls.append(cfg)
            raise KeyboardInterrupt

        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", mock_bootstrap)
        monkeypatch.setattr("gasclaw.cli.monitor_loop", mock_monitor)

        runner.invoke(
            app, ["start", "--gt-root", str(tmp_path), "--project-dir", str(project_override)]
        )

        assert len(monitor_calls) == 1
        assert monitor_calls[0].project_dir == str(project_override)
        # KeyboardInterrupt causes exit code 130, which is expected

    def test_start_exits_on_bootstrap_failure(self, config, monkeypatch, tmp_path):
        """start command exits with code 1 if bootstrap raises an exception."""

        def mock_bootstrap_fail(cfg, gt_root):
            raise RuntimeError("dolt connection failed")

        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", mock_bootstrap_fail)

        result = runner.invoke(app, ["start", "--gt-root", str(tmp_path)])

        assert result.exit_code == 1
        assert "Bootstrap failed" in result.output
        assert "dolt connection failed" in result.output

    def test_start_exits_on_keyboard_interrupt(self, config, monkeypatch, tmp_path):
        """start command exits with code 130 if bootstrap is interrupted."""

        def mock_bootstrap_interrupt(cfg, gt_root):
            raise KeyboardInterrupt()

        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", mock_bootstrap_interrupt)

        result = runner.invoke(app, ["start", "--gt-root", str(tmp_path)])

        assert result.exit_code == 130
        assert "interrupted" in result.output.lower()

    def test_start_monitor_loop_keyboard_interrupt(self, config, monkeypatch, tmp_path):
        """start command handles KeyboardInterrupt in monitor_loop (lines 88-91)."""

        def mock_bootstrap(cfg, gt_root):
            pass

        def mock_monitor_interrupt(cfg):
            raise KeyboardInterrupt()

        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", mock_bootstrap)
        monkeypatch.setattr("gasclaw.cli.monitor_loop", mock_monitor_interrupt)

        result = runner.invoke(app, ["start", "--gt-root", str(tmp_path)])

        assert result.exit_code == 0
        assert "Shutting down" in result.output or "shutting down" in result.output.lower()


class TestStopCommand:
    def test_calls_stop_all(self, monkeypatch):
        """stop command calls stop_all."""
        calls = []
        monkeypatch.setattr("gasclaw.cli.stop_all", lambda: calls.append(1))

        result = runner.invoke(app, ["stop"])

        assert len(calls) == 1
        assert result.exit_code == 0
        assert "Stopping all services" in result.output
        assert "All services stopped" in result.output

    def test_stop_command_prints_messages(self, monkeypatch):
        """stop command prints start and stop messages (lines 97, 99)."""
        monkeypatch.setattr("gasclaw.cli.stop_all", lambda: None)

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        assert "Stopping all services..." in result.output
        assert "All services stopped" in result.output

    def test_stop_exits_on_exception(self, monkeypatch):
        """stop command exits with code 1 if stop_all raises an exception (lines 103-106)."""

        def mock_stop_fail():
            raise RuntimeError("service not running")

        monkeypatch.setattr("gasclaw.cli.stop_all", mock_stop_fail)

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 1
        assert "Error stopping services" in result.output
        assert "service not running" in result.output


class TestStatusCommand:
    def test_shows_health_status(self, monkeypatch):
        """status command displays health report."""
        from gasclaw.health import HealthReport

        def mock_check_health(**kw):
            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor", "crew-1"],
            )

        def raise_valueerror():
            raise ValueError("no config")

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr("gasclaw.cli.load_config", raise_valueerror)

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Gasclaw Status" in result.output
        assert "healthy" in result.output

    def test_shows_activity_when_config_loaded(self, config, monkeypatch):
        """status command shows activity when config is available."""
        from gasclaw.health import HealthReport

        def mock_check_health(**kw):
            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "gasclaw.cli.check_agent_activity",
            lambda **kw: {"compliant": True, "last_commit_age": 300},
        )
        def mock_status():
            return {"total": 2, "available": 2, "rate_limited": 0}

        monkeypatch.setattr(
            "gasclaw.cli.KeyPool",
            MagicMock(return_value=MagicMock(status=mock_status)),
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "compliant" in result.output.lower() or "activity" in result.output.lower()


class TestUpdateCommand:
    def test_shows_versions_and_updates(self, monkeypatch):
        """update command checks versions and applies updates."""
        monkeypatch.setattr(
            "gasclaw.cli.check_versions", lambda: {"gt": "1.0.0", "claude": "2.0.0"}
        )
        monkeypatch.setattr(
            "gasclaw.cli.apply_updates", lambda: {"gt": "updated", "claude": "up-to-date"}
        )

        result = runner.invoke(app, ["update"])

        assert result.exit_code == 0
        assert "Checking versions" in result.output
        assert "gt:" in result.output
        assert "Applying updates" in result.output


class TestVersionCommand:
    def test_version_flag_shows_version(self):
        """--version flag displays version and exits."""
        from gasclaw import __version__

        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_command_shows_version(self):
        """version subcommand displays version."""
        from gasclaw import __version__

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert __version__ in result.output

    def test_version_matches_pyproject_toml(self):
        """__version__ matches the version in pyproject.toml."""
        import tomllib

        from gasclaw import __version__

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        expected_version = pyproject["project"]["version"]
        assert __version__ == expected_version, (
            f"Version mismatch: __init__.py has '{__version__}', "
            f"pyproject.toml has '{expected_version}'"
        )


class TestCLIEdgeCases:
    def test_help_flag_shows_help(self):
        """Running with --help shows help text."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Gasclaw" in result.output

    def test_start_help_shows_options(self):
        """start --help shows available options."""
        result = runner.invoke(app, ["start", "--help"])
        assert result.exit_code == 0
        assert "--gt-root" in result.output

    def test_invalid_command_fails(self):
        """Invalid command name exits with error."""
        result = runner.invoke(app, ["invalidcommand"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Error" in result.output

    def test_start_with_invalid_gt_root_type(self):
        """start with non-path argument handles gracefully."""
        result = runner.invoke(app, ["start", "--gt-root", ""])
        # Should not crash, will use default/empty path
        assert result.exit_code == 1  # Config error expected since env vars not set

    def test_status_shows_unhealthy_services(self, monkeypatch):
        """status command shows unhealthy services in red."""
        from gasclaw.health import HealthReport

        def mock_check_health(**kw):
            return HealthReport(
                dolt="unhealthy",
                daemon="healthy",
                mayor="unhealthy",
                openclaw="unknown",
                agents=[],
            )

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr(
            "gasclaw.cli.load_config", lambda: (_ for _ in ()).throw(ValueError("no config"))
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "unhealthy" in result.output
        assert "healthy" in result.output
        assert "unknown" in result.output

    def test_status_shows_non_compliant_activity(self, config, monkeypatch):
        """status command shows NOT COMPLIANT when activity check fails."""
        from gasclaw.health import HealthReport

        def mock_check_health(**kw):
            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "gasclaw.cli.check_agent_activity",
            lambda **kw: {"compliant": False, "last_commit_age": 5000},
        )
        monkeypatch.setattr(
            "gasclaw.cli.KeyPool",
            MagicMock(return_value=MagicMock(status=lambda: {"total": 2, "available": 1})),
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "NOT COMPLIANT" in result.output or "not compliant" in result.output.lower()

    def test_status_shows_rate_limited_count(self, config, monkeypatch):
        """status command shows rate_limited count when keys are rate limited."""
        from gasclaw.health import HealthReport

        def mock_check_health(**kw):
            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "gasclaw.cli.check_agent_activity",
            lambda **kw: {"compliant": True, "last_commit_age": 300},
        )
        def mock_status_rl():
            return {"total": 5, "available": 3, "rate_limited": 2}

        monkeypatch.setattr(
            "gasclaw.cli.KeyPool",
            MagicMock(return_value=MagicMock(status=mock_status_rl)),
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "3/5 available" in result.output
        assert "2 rate-limited" in result.output


class TestMigrateCommand:
    """Tests for migrate command (lines 193-210)."""

    def test_migrate_successful(self, tmp_path, monkeypatch):
        """migrate command succeeds when migration is successful."""
        from gasclaw.migration import MigrationResult

        def mock_migrate(*args, **kwargs):
            return MigrationResult(
                success=True,
                dry_run=False,
                gastown_detected=True,
                migrated_keys=["KIMI_API_KEY"],
                env_file_path=tmp_path / ".env",
            )

        monkeypatch.setattr("gasclaw.cli.run_migration", mock_migrate)

        result = runner.invoke(app, ["migrate"])

        assert result.exit_code == 0
        assert "Migration complete" in result.output
        assert "Next steps" in result.output

    def test_migrate_successful_dry_run(self, tmp_path, monkeypatch):
        """migrate --dry-run shows summary without next steps."""
        from gasclaw.migration import MigrationResult

        def mock_migrate(*args, **kwargs):
            return MigrationResult(
                success=True,
                dry_run=True,
                gastown_detected=True,
            )

        monkeypatch.setattr("gasclaw.cli.run_migration", mock_migrate)

        result = runner.invoke(app, ["migrate", "--dry-run"])

        assert result.exit_code == 0
        assert "DRY RUN" in result.output or "dry run" in result.output.lower()

    def test_migrate_failure_exits_with_code_1(self, tmp_path, monkeypatch):
        """migrate command exits with code 1 when migration fails (lines 209-210)."""
        from gasclaw.migration import MigrationResult

        def mock_migrate(*args, **kwargs):
            return MigrationResult(
                success=False,
                dry_run=False,
                gastown_detected=False,
                error_message="No Gastown installation found",
            )

        monkeypatch.setattr("gasclaw.cli.run_migration", mock_migrate)

        result = runner.invoke(app, ["migrate"])

        assert result.exit_code == 1

    def test_migrate_displays_checking_message(self, monkeypatch):
        """migrate command displays 'Checking for Gastown' message (line 193)."""
        from gasclaw.migration import MigrationResult

        def mock_migrate(*args, **kwargs):
            return MigrationResult(
                success=True,
                dry_run=False,
                gastown_detected=True,
                migrated_keys=["KIMI_API_KEY"],
            )

        monkeypatch.setattr("gasclaw.cli.run_migration", mock_migrate)

        result = runner.invoke(app, ["migrate"])

        assert "Checking for Gastown" in result.output

    def test_migrate_accepts_custom_paths(self, tmp_path, monkeypatch):
        """migrate command accepts custom gastown-dir and env-file paths."""
        from gasclaw.migration import MigrationResult

        migrate_calls = []

        def mock_migrate(**kwargs):
            migrate_calls.append(kwargs)
            return MigrationResult(
                success=True,
                dry_run=False,
                gastown_detected=True,
            )

        monkeypatch.setattr("gasclaw.cli.run_migration", mock_migrate)

        gt_dir = tmp_path / "custom_gt"
        env_file = tmp_path / "custom.env"

        result = runner.invoke(
            app,
            [
                "migrate",
                "--gastown-dir",
                str(gt_dir),
                "--env-file",
                str(env_file),
            ],
        )

        assert result.exit_code == 0
        assert len(migrate_calls) == 1
        assert migrate_calls[0]["gastown_dir"] == gt_dir
        assert migrate_calls[0]["gasclaw_env_file"] == env_file


class TestMaintainCommand:
    def test_maintain_once_runs_single_cycle(self, monkeypatch):
        """maintain --once runs a single maintenance cycle."""
        cycle_calls = []
        monkeypatch.setattr(
            "gasclaw.cli.run_maintenance_cycle", lambda: cycle_calls.append({"prs": {"merged": 1}})
        )

        result = runner.invoke(app, ["maintain", "--once"])

        assert len(cycle_calls) == 1
        assert result.exit_code == 0
        assert "Cycle complete" in result.output

    def test_maintain_once_exits_on_failure(self, monkeypatch):
        """maintain --once exits with error on failure."""

        def fail_cycle():
            raise RuntimeError("API error")

        monkeypatch.setattr("gasclaw.cli.run_maintenance_cycle", fail_cycle)

        result = runner.invoke(app, ["maintain", "--once"])

        assert result.exit_code == 1
        assert "Maintenance failed" in result.output

    def test_maintain_loop_starts_continuous_loop(self, monkeypatch):
        """maintain without --once starts continuous loop."""
        loop_calls = []

        def mock_loop(interval):
            loop_calls.append(interval)
            raise KeyboardInterrupt  # Simulate user stop

        monkeypatch.setattr("gasclaw.cli.maintenance_loop", mock_loop)

        result = runner.invoke(app, ["maintain", "--interval", "60"])

        assert len(loop_calls) == 1
        assert loop_calls[0] == 60
        assert "stopped" in result.output.lower()

    def test_maintain_default_interval(self, monkeypatch):
        """maintain uses default interval of 300 seconds."""
        loop_calls = []

        def mock_loop(interval):
            loop_calls.append(interval)
            raise KeyboardInterrupt

        monkeypatch.setattr("gasclaw.cli.maintenance_loop", mock_loop)

        runner.invoke(app, ["maintain"])

        assert loop_calls[0] == 300

    def test_maintain_keyboard_interrupt_handling(self, monkeypatch):
        """maintain command handles KeyboardInterrupt gracefully (lines 184-187)."""

        def mock_loop(interval):
            raise KeyboardInterrupt

        monkeypatch.setattr("gasclaw.cli.maintenance_loop", mock_loop)

        result = runner.invoke(app, ["maintain"])

        assert result.exit_code == 0
        assert "stopped" in result.output.lower() or "Maintenance loop stopped" in result.output

    def test_maintain_displays_start_message(self, monkeypatch):
        """maintain command displays start message (line 170, 182-183)."""
        loop_calls = []

        def mock_loop(interval):
            loop_calls.append(interval)
            raise KeyboardInterrupt

        monkeypatch.setattr("gasclaw.cli.maintenance_loop", mock_loop)

        result = runner.invoke(app, ["maintain", "--interval", "60"])

        assert result.exit_code == 0
        assert (
            "Entering maintenance loop" in result.output or "Starting maintenance" in result.output
        )
        assert "interval=60" in result.output or "60s" in result.output

    def test_maintain_rejects_zero_interval(self):
        """maintain command rejects --interval 0."""
        result = runner.invoke(app, ["maintain", "--interval", "0"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "0" in result.output

    def test_maintain_rejects_negative_interval(self):
        """maintain command rejects negative --interval values."""
        result = runner.invoke(app, ["maintain", "--interval", "-1"])

        assert result.exit_code != 0
        assert "Invalid value" in result.output or "-1" in result.output
