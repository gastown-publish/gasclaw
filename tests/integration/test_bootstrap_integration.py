"""Integration tests for gasclaw.bootstrap.

These tests verify that bootstrap correctly orchestrates all subsystems
with mocked external dependencies (HTTP APIs, subprocess calls).
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from gasclaw.bootstrap import bootstrap, monitor_loop
from gasclaw.config import GasclawConfig
from gasclaw.openclaw.doctor import DoctorResult


@pytest.fixture
def config():
    """Create a test configuration."""
    return GasclawConfig(
        gastown_kimi_keys=["sk-key1", "sk-key2", "sk-key3"],
        openclaw_kimi_key="sk-openclaw",
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_owner_id="123456789",
        gt_rig_url="/test/project",
        project_dir="/test/project",
        monitor_interval=60,
        activity_deadline=1800,
    )


@pytest.fixture
def mock_subprocess_success(monkeypatch):
    """Mock all subprocess calls to succeed."""

    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout=b"ok", stderr=b"")

    def mock_popen(*args, **kwargs):
        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.poll.return_value = None
        mock_proc.returncode = 0
        return mock_proc

    monkeypatch.setattr(subprocess, "run", mock_run)
    monkeypatch.setattr(subprocess, "Popen", mock_popen)


class TestBootstrapIntegration:
    """Integration tests for the bootstrap sequence."""

    def test_full_bootstrap_with_http_mocking(self, config, tmp_path, monkeypatch):
        """Test complete bootstrap with respx mocking HTTP calls."""
        gt_root = tmp_path / "gt"
        gt_root.mkdir()

        # Track all the calls to verify integration
        calls = {
            "kimi_accounts": False,
            "agent_config": False,
            "gastown_install": False,
            "dolt_start": False,
            "openclaw_config": False,
            "skills_install": False,
            "doctor": False,
            "daemon_start": False,
            "mayor_start": False,
            "telegram_notify": False,
        }

        mock_doctor = DoctorResult(healthy=True, returncode=0, output="All checks passed")

        with patch("gasclaw.bootstrap.setup_kimi_accounts") as m_kimi:
            m_kimi.side_effect = lambda keys: calls.update({"kimi_accounts": True})
            with patch("gasclaw.bootstrap.write_agent_config") as m_agent:
                m_agent.side_effect = lambda path: calls.update({"agent_config": True})
                with patch("gasclaw.bootstrap.gastown_install") as m_install:
                    m_install.side_effect = lambda **kw: calls.update({"gastown_install": True})
                    with patch("gasclaw.bootstrap.start_dolt") as m_dolt:
                        m_dolt.side_effect = lambda: calls.update({"dolt_start": True})
                        with patch("gasclaw.bootstrap.write_openclaw_config") as m_oc:
                            m_oc.side_effect = lambda **kw: calls.update({"openclaw_config": True})
                            with patch("gasclaw.bootstrap.install_skills") as m_skills:
                                m_skills.side_effect = lambda **kw: calls.update(
                                    {"skills_install": True}
                                )
                                with patch(
                                    "gasclaw.bootstrap.run_doctor", return_value=mock_doctor
                                ) as m_doctor:

                                    def doctor_side_effect(**kw):
                                        calls.update({"doctor": True})
                                        return mock_doctor

                                    m_doctor.side_effect = doctor_side_effect
                                    with patch("gasclaw.bootstrap.start_daemon") as m_daemon:
                                        m_daemon.side_effect = lambda: calls.update(
                                            {"daemon_start": True}
                                        )
                                        with patch("gasclaw.bootstrap.start_mayor") as m_mayor:
                                            m_mayor.side_effect = lambda **kw: calls.update(
                                                {"mayor_start": True}
                                            )
                                            with respx.mock:
                                                # Mock Telegram gateway
                                                respx.post(
                                                    "http://localhost:18789/api/message"
                                                ).mock(
                                                    return_value=Response(200, json={"ok": True})
                                                )
                                                with patch(
                                                    "gasclaw.bootstrap.notify_telegram"
                                                ) as m_notify:

                                                    def notify_side_effect(msg):
                                                        calls.update({"telegram_notify": True})

                                                    m_notify.side_effect = notify_side_effect

                                                    # Run bootstrap
                                                    bootstrap(config, gt_root=gt_root)

        # Verify all subsystems were called
        assert all(calls.values()), f"Not all subsystems called: {calls}"

    def test_bootstrap_with_doctor_issues(self, config, tmp_path):
        """Test bootstrap handles doctor issues gracefully."""
        gt_root = tmp_path / "gt"
        gt_root.mkdir()

        # Doctor reports issues but bootstrap continues
        mock_doctor = DoctorResult(
            healthy=False, returncode=1, output="Config issue: missing skill"
        )

        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts"),
            patch("gasclaw.bootstrap.write_agent_config"),
            patch("gasclaw.bootstrap.gastown_install"),
            patch("gasclaw.bootstrap.start_dolt"),
            patch("gasclaw.bootstrap.write_openclaw_config"),
            patch("gasclaw.bootstrap.install_skills"),
            patch("gasclaw.bootstrap.run_doctor", return_value=mock_doctor) as m_doctor,
            patch("gasclaw.bootstrap.start_daemon") as m_daemon,
            patch("gasclaw.bootstrap.start_mayor") as m_mayor,
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
        ):
            bootstrap(config, gt_root=gt_root)

            # Doctor should be called with repair=True
            m_doctor.assert_called_once_with(repair=True)
            # Should notify about issues
            m_notify.assert_called()
            # Bootstrap should continue despite issues
            m_daemon.assert_called_once()
            m_mayor.assert_called_once()

    def test_bootstrap_service_ordering(self, config, tmp_path):
        """Test that services start in correct dependency order."""
        gt_root = tmp_path / "gt"
        gt_root.mkdir()

        call_order = []
        mock_doctor = DoctorResult(healthy=True, returncode=0, output="OK")

        def track_call(name):
            def wrapper(*args, **kwargs):
                call_order.append(name)

            return wrapper

        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts", side_effect=track_call("kimi")),
            patch("gasclaw.bootstrap.write_agent_config", side_effect=track_call("agent_config")),
            patch("gasclaw.bootstrap.gastown_install", side_effect=track_call("install")),
            patch("gasclaw.bootstrap.start_dolt", side_effect=track_call("dolt")),
            patch(
                "gasclaw.bootstrap.write_openclaw_config", side_effect=track_call("openclaw_config")
            ),
            patch("gasclaw.bootstrap.install_skills", side_effect=track_call("skills")),
            patch(
                "gasclaw.bootstrap.run_doctor",
                side_effect=lambda **kw: (track_call("doctor")(kw), mock_doctor)[1],
            ),
            patch("gasclaw.bootstrap.start_daemon", side_effect=track_call("daemon")),
            patch("gasclaw.bootstrap.start_mayor", side_effect=track_call("mayor")),
            patch("gasclaw.bootstrap.notify_telegram", side_effect=track_call("notify")),
        ):
            bootstrap(config, gt_root=gt_root)

        # Verify critical ordering constraints
        assert call_order.index("kimi") < call_order.index("install")
        assert call_order.index("install") < call_order.index("dolt")
        assert call_order.index("dolt") < call_order.index("daemon")
        assert call_order.index("skills") < call_order.index("doctor")
        assert call_order.index("doctor") < call_order.index("daemon")
        assert call_order.index("daemon") < call_order.index("mayor")
        assert call_order.index("mayor") < call_order.index("notify")


class TestMonitorLoopIntegration:
    """Integration tests for the monitor loop."""

    def test_monitor_loop_health_check_cycle(self, config, monkeypatch):
        """Test monitor loop runs health checks in a cycle."""
        health_calls = []
        activity_calls = []

        def mock_check_health(**kw):
            health_calls.append(1)
            if len(health_calls) >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport

            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        def mock_check_activity(**kw):
            activity_calls.append(kw)
            return {"compliant": True, "last_commit_age": 300}

        monkeypatch.setattr("gasclaw.bootstrap.check_health", mock_check_health)
        monkeypatch.setattr("gasclaw.bootstrap.check_agent_activity", mock_check_activity)
        monkeypatch.setattr("gasclaw.bootstrap.notify_telegram", lambda msg: None)
        monkeypatch.setattr("time.sleep", lambda x: None)

        monitor_loop(config, interval=1)

        assert len(health_calls) >= 1
        assert len(activity_calls) >= 1

    def test_monitor_loop_notifies_on_unhealthy_service(self, config, monkeypatch):
        """Test monitor loop notifies when a service is unhealthy."""
        notifications = []
        call_count = [0]

        def mock_check_health(**kw):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport

            return HealthReport(
                dolt="healthy",
                daemon="unhealthy",  # Service down
                mayor="healthy",
                openclaw="healthy",
                agents=[],
            )

        monkeypatch.setattr("gasclaw.bootstrap.check_health", mock_check_health)
        monkeypatch.setattr(
            "gasclaw.bootstrap.check_agent_activity",
            lambda **kw: {"compliant": True, "last_commit_age": 300},
        )
        monkeypatch.setattr(
            "gasclaw.bootstrap.notify_telegram", lambda msg: notifications.append(msg)
        )
        monkeypatch.setattr("time.sleep", lambda x: None)

        monitor_loop(config, interval=1)

        # Should have notified about unhealthy daemon
        assert any(
            "daemon" in msg.lower() or "service down" in msg.lower() for msg in notifications
        )

    def test_monitor_loop_notifies_on_activity_violation(self, config, monkeypatch):
        """Test monitor loop notifies when activity deadline is violated."""
        notifications = []
        call_count = [0]

        def mock_check_health(**kw):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport

            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        monkeypatch.setattr("gasclaw.bootstrap.check_health", mock_check_health)
        monkeypatch.setattr(
            "gasclaw.bootstrap.check_agent_activity",
            lambda **kw: {"compliant": False, "last_commit_age": 5000},  # Not compliant
        )
        monkeypatch.setattr(
            "gasclaw.bootstrap.notify_telegram", lambda msg: notifications.append(msg)
        )
        monkeypatch.setattr("time.sleep", lambda x: None)

        monitor_loop(config, interval=1)

        # Should have notified about activity violation
        assert any("activity" in msg.lower() or "alert" in msg.lower() for msg in notifications)

    @respx.mock
    def test_monitor_loop_with_http_notification(self, config, monkeypatch):
        """Test monitor loop sends HTTP notifications via gateway."""
        # Mock the gateway endpoint
        respx.post("http://localhost:18789/api/message").mock(
            return_value=Response(200, json={"ok": True})
        )

        call_count = [0]

        def mock_check_health(**kw):
            call_count[0] += 1
            if call_count[0] >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport

            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        monkeypatch.setattr("gasclaw.bootstrap.check_health", mock_check_health)
        monkeypatch.setattr(
            "gasclaw.bootstrap.check_agent_activity",
            lambda **kw: {"compliant": True, "last_commit_age": 300},
        )
        monkeypatch.setattr("time.sleep", lambda x: None)

        # Use actual notify_telegram which makes HTTP calls
        monitor_loop(config, interval=1)

    def test_monitor_loop_uses_config_interval(self, config, monkeypatch):
        """Test monitor loop respects configured interval."""
        sleep_calls = []
        call_count = [0]

        def mock_sleep(seconds):
            sleep_calls.append(seconds)
            call_count[0] += 1
            if call_count[0] >= 2:
                raise KeyboardInterrupt

        monkeypatch.setattr(
            "gasclaw.bootstrap.check_health",
            lambda **kw: type(
                "R",
                (),
                {
                    "dolt": "healthy",
                    "daemon": "healthy",
                    "mayor": "healthy",
                    "openclaw": "healthy",
                    "agents": [],
                },
            )(),
        )
        monkeypatch.setattr(
            "gasclaw.bootstrap.check_agent_activity",
            lambda **kw: {"compliant": True, "last_commit_age": 300},
        )
        monkeypatch.setattr("gasclaw.bootstrap.notify_telegram", lambda msg: None)
        monkeypatch.setattr("time.sleep", mock_sleep)

        custom_interval = 120
        monitor_loop(config, interval=custom_interval)

        assert all(s == custom_interval for s in sleep_calls)
