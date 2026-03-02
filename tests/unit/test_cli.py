"""Tests for gasclaw.cli."""

from __future__ import annotations

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
            app,
            ["start", "--gt-root", str(tmp_path), "--project-dir", str(project_override)]
        )

        assert len(monitor_calls) == 1
        assert monitor_calls[0].project_dir == str(project_override)
        # KeyboardInterrupt causes exit code 130, which is expected


class TestStopCommand:
    def test_calls_stop_all(self, monkeypatch):
        """stop command calls stop_all."""
        calls = []
        monkeypatch.setattr("gasclaw.cli.stop_all", lambda: calls.append(1))

        result = runner.invoke(app, ["stop"])

        assert len(calls) == 1
        assert result.exit_code == 0
        assert "Stopping all services" in result.output


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
        monkeypatch.setattr(
            "gasclaw.cli.KeyPool",
            MagicMock(return_value=MagicMock(status=lambda: {"total": 2, "available": 2})),
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
