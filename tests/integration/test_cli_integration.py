"""Integration tests for gasclaw.cli.

These tests verify CLI commands work correctly with mocked dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import respx
from httpx import Response
from typer.testing import CliRunner

from gasclaw.cli import app
from gasclaw.config import GasclawConfig

runner = CliRunner()


@pytest.fixture
def config():
    """Create a test configuration."""
    return GasclawConfig(
        gastown_kimi_keys=["sk-key1", "sk-key2"],
        openclaw_kimi_key="sk-oc",
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_owner_id="123456789",
        gt_rig_url="/test/project",
        project_dir="/test/project",
        monitor_interval=60,
        activity_deadline=1800,
    )


class TestStartCommandIntegration:
    """Integration tests for the start command."""

    def test_start_full_workflow(self, config, monkeypatch, tmp_path):
        """Test start command runs full bootstrap and monitor workflow."""
        bootstrap_called = []
        monitor_called = []

        def mock_bootstrap(cfg, gt_root):
            bootstrap_called.append((cfg, gt_root))

        def mock_monitor(cfg):
            monitor_called.append(cfg)
            raise KeyboardInterrupt  # Exit after one iteration

        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", mock_bootstrap)
        monkeypatch.setattr("gasclaw.cli.monitor_loop", mock_monitor)

        result = runner.invoke(app, ["start", "--gt-root", str(tmp_path)])

        # KeyboardInterrupt causes exit code 130 (128 + SIGINT)
        assert result.exit_code in (0, 130)
        assert len(bootstrap_called) == 1
        assert bootstrap_called[0][1] == tmp_path
        assert len(monitor_called) == 1
        assert "Starting gasclaw" in result.output
        assert "All services started" in result.output

    def test_start_with_config_error(self, monkeypatch):
        """Test start command handles config loading errors."""
        monkeypatch.setattr(
            "gasclaw.cli.load_config",
            lambda: (_ for _ in ()).throw(ValueError("Missing required env: TEST_KEY")),
        )

        result = runner.invoke(app, ["start"])

        assert result.exit_code == 1
        assert "Config error" in result.output

    def test_start_with_bootstrap_failure(self, config, monkeypatch, tmp_path):
        """Test start command handles bootstrap failures."""
        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr(
            "gasclaw.cli.bootstrap",
            lambda cfg, gt_root: (_ for _ in ()).throw(RuntimeError("Bootstrap failed")),
        )

        result = runner.invoke(app, ["start", "--gt-root", str(tmp_path)])

        assert result.exit_code != 0
        assert "Bootstrap failed" in result.output or result.exit_code == 1


class TestStopCommandIntegration:
    """Integration tests for the stop command."""

    def test_stop_calls_all_services(self, monkeypatch):
        """Test stop command stops all services."""
        stop_calls = []
        monkeypatch.setattr("gasclaw.cli.stop_all", lambda: stop_calls.append(1))

        result = runner.invoke(app, ["stop"])

        assert result.exit_code == 0
        assert len(stop_calls) == 1
        assert "Stopping all services" in result.output
        assert "All services stopped" in result.output

    def test_stop_handles_errors_gracefully(self, monkeypatch):
        """Test stop command handles service stop errors."""

        def failing_stop():
            raise RuntimeError("Service stop failed")

        monkeypatch.setattr("gasclaw.cli.stop_all", failing_stop)

        result = runner.invoke(app, ["stop"])

        # Should propagate error
        assert result.exit_code != 0


class TestStatusCommandIntegration:
    """Integration tests for the status command."""

    def test_status_shows_all_services_healthy(self, monkeypatch):
        """Test status command with all services healthy."""
        from gasclaw.health import HealthReport

        def mock_check_health(**kw):
            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                openclaw_doctor="healthy",
                agents=["mayor", "deacon", "witness"],
                key_pool={"total": 5, "available": 5},
                activity={"compliant": True, "last_commit_age": 300},
            )

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr(
            "gasclaw.cli.load_config", lambda: (_ for _ in ()).throw(ValueError("no config"))
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Gasclaw Status" in result.output
        assert "healthy" in result.output
        assert "mayor" in result.output.lower() or "agents" in result.output.lower()

    def test_status_shows_unhealthy_services(self, monkeypatch):
        """Test status command shows unhealthy services in red."""
        from gasclaw.health import HealthReport

        def mock_check_health(**kw):
            return HealthReport(
                dolt="unhealthy",
                daemon="healthy",
                mayor="unhealthy",
                openclaw="healthy",
                agents=[],
            )

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr(
            "gasclaw.cli.load_config", lambda: (_ for _ in ()).throw(ValueError("no config"))
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "unhealthy" in result.output

    def test_status_with_full_config(self, config, monkeypatch):
        """Test status command with config loaded shows all info."""
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
            lambda **kw: {"compliant": True, "last_commit_age": 600},
        )
        monkeypatch.setattr(
            "gasclaw.cli.KeyPool",
            MagicMock(return_value=MagicMock(status=lambda: {"total": 3, "available": 2})),
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "Gasclaw Status" in result.output
        # Should show activity status
        assert "compliant" in result.output.lower() or "activity" in result.output.lower()
        # Should show key pool
        assert "key pool" in result.output.lower() or "available" in result.output.lower()

    def test_status_with_activity_violation(self, config, monkeypatch):
        """Test status command shows activity violations."""
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
            MagicMock(return_value=MagicMock(status=lambda: {"total": 3, "available": 3})),
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        # Should show non-compliant status
        assert "not compliant" in result.output.lower() or "non-compliant" in result.output.lower()


class TestUpdateCommandIntegration:
    """Integration tests for the update command."""

    def test_update_checks_and_applies(self, monkeypatch):
        """Test update command checks versions and applies updates."""
        monkeypatch.setattr(
            "gasclaw.cli.check_versions",
            lambda: {"gt": "1.0.0", "claude": "2.0.0", "openclaw": "0.5.0"},
        )
        monkeypatch.setattr(
            "gasclaw.cli.apply_updates",
            lambda: {"gt": "updated", "claude": "up-to-date", "openclaw": "updated"},
        )

        result = runner.invoke(app, ["update"])

        assert result.exit_code == 0
        assert "Checking versions" in result.output
        assert "gt:" in result.output
        assert "claude:" in result.output
        assert "Applying updates" in result.output
        assert "updated" in result.output or "up-to-date" in result.output

    def test_update_with_failed_updates(self, monkeypatch):
        """Test update command handles failed updates."""
        monkeypatch.setattr(
            "gasclaw.cli.check_versions", lambda: {"gt": "1.0.0", "claude": "not installed"}
        )
        monkeypatch.setattr(
            "gasclaw.cli.apply_updates",
            lambda: {"gt": "updated", "claude": "failed: network error"},
        )

        result = runner.invoke(app, ["update"])

        assert result.exit_code == 0
        # Should show both successful and failed updates
        assert "updated" in result.output
        assert "failed" in result.output.lower() or "error" in result.output.lower()

    def test_update_with_empty_results(self, monkeypatch):
        """Test update command handles empty version results."""
        monkeypatch.setattr("gasclaw.cli.check_versions", lambda: {})
        monkeypatch.setattr("gasclaw.cli.apply_updates", lambda: {})

        result = runner.invoke(app, ["update"])

        assert result.exit_code == 0
        assert "Checking versions" in result.output
        assert "Applying updates" in result.output


class TestCLIWithHTTPMocking:
    """Integration tests using respx for HTTP mocking."""

    @respx.mock
    def test_status_with_gateway_http_check(self, monkeypatch):
        """Test status command with HTTP gateway health check."""
        from gasclaw.health import HealthReport

        # Mock the gateway health endpoint
        respx.get("http://localhost:18789/health").mock(return_value=Response(200, text="healthy"))

        def mock_check_health(**kw):
            # Simulate the actual health check that would use HTTP
            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",  # Would be determined by HTTP check
                agents=["mayor"],
            )

        monkeypatch.setattr("gasclaw.cli.check_health", mock_check_health)
        monkeypatch.setattr(
            "gasclaw.cli.load_config", lambda: (_ for _ in ()).throw(ValueError("no config"))
        )

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "healthy" in result.output


class TestCLIErrorHandling:
    """Integration tests for CLI error handling."""

    def test_cli_handles_keyboard_interrupt(self, config, monkeypatch, tmp_path):
        """Test CLI handles keyboard interrupt gracefully."""
        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", lambda cfg, gt_root: None)
        monkeypatch.setattr(
            "gasclaw.cli.monitor_loop", lambda cfg: (_ for _ in ()).throw(KeyboardInterrupt)
        )

        result = runner.invoke(app, ["start", "--gt-root", str(tmp_path)])

        # KeyboardInterrupt should be handled gracefully
        assert result.exit_code == 0

    def test_start_with_custom_gt_root(self, config, monkeypatch, tmp_path):
        """Test start command with custom gt-root option."""
        captured_gt_root = []

        def mock_bootstrap(cfg, gt_root):
            captured_gt_root.append(gt_root)

        def mock_monitor(cfg):
            raise KeyboardInterrupt

        monkeypatch.setattr("gasclaw.cli.load_config", lambda: config)
        monkeypatch.setattr("gasclaw.cli.bootstrap", mock_bootstrap)
        monkeypatch.setattr("gasclaw.cli.monitor_loop", mock_monitor)

        custom_path = tmp_path / "custom" / "gt"
        custom_path.mkdir(parents=True)

        result = runner.invoke(app, ["start", "--gt-root", str(custom_path)])

        assert result.exit_code == 0
        assert len(captured_gt_root) == 1
        assert captured_gt_root[0] == custom_path
