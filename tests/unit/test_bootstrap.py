"""Tests for gasclaw.bootstrap."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from gasclaw.bootstrap import bootstrap, monitor_loop
from gasclaw.config import GasclawConfig


@pytest.fixture
def config():
    return GasclawConfig(
        gastown_kimi_keys=["sk-key1", "sk-key2"],
        openclaw_kimi_key="sk-oc",
        telegram_bot_token="123:ABC",
        telegram_owner_id="999",
    )


class TestBootstrap:
    def test_calls_all_subsystems(self, config, monkeypatch, tmp_path):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        monkeypatch.setattr(
            subprocess, "Popen",
            lambda *a, **kw: type("P", (), {"pid": 1, "poll": lambda s: None})(),
        )

        from gasclaw.openclaw.doctor import DoctorResult
        mock_doctor = DoctorResult(healthy=True, returncode=0, output="OK")

        with patch("gasclaw.bootstrap.setup_kimi_accounts") as m_kimi, \
             patch("gasclaw.bootstrap.write_agent_config") as m_agent, \
             patch("gasclaw.bootstrap.gastown_install") as m_install, \
             patch("gasclaw.bootstrap.start_dolt") as m_dolt, \
             patch("gasclaw.bootstrap.write_openclaw_config") as m_oc, \
             patch("gasclaw.bootstrap.install_skills") as m_skills, \
             patch("gasclaw.bootstrap.run_doctor", return_value=mock_doctor) as m_doctor, \
             patch("gasclaw.bootstrap.start_daemon") as m_daemon, \
             patch("gasclaw.bootstrap.start_mayor") as m_mayor, \
             patch("gasclaw.bootstrap.notify_telegram") as m_notify:

            bootstrap(config, gt_root=tmp_path)

            m_kimi.assert_called_once()
            m_agent.assert_called_once()
            m_install.assert_called_once()
            m_dolt.assert_called_once()
            m_oc.assert_called_once()
            m_skills.assert_called_once()
            m_doctor.assert_called_once()
            m_daemon.assert_called_once()
            m_mayor.assert_called_once()
            m_notify.assert_called_once()

    def test_call_order(self, config, monkeypatch, tmp_path):
        order = []

        from gasclaw.openclaw.doctor import DoctorResult
        mock_doctor = DoctorResult(healthy=True, returncode=0, output="OK")

        def doctor_side_effect(**kw):
            order.append("doctor")
            return mock_doctor

        def se(name):
            return lambda *a, **kw: order.append(name)

        with patch("gasclaw.bootstrap.setup_kimi_accounts", side_effect=se("kimi")), \
             patch("gasclaw.bootstrap.write_agent_config", side_effect=se("agent_config")), \
             patch("gasclaw.bootstrap.gastown_install", side_effect=se("install")), \
             patch("gasclaw.bootstrap.start_dolt", side_effect=se("dolt")), \
             patch("gasclaw.bootstrap.write_openclaw_config", side_effect=se("openclaw")), \
             patch("gasclaw.bootstrap.install_skills", side_effect=se("skills")), \
             patch("gasclaw.bootstrap.run_doctor", side_effect=doctor_side_effect), \
             patch("gasclaw.bootstrap.start_daemon", side_effect=se("daemon")), \
             patch("gasclaw.bootstrap.start_mayor", side_effect=se("mayor")), \
             patch("gasclaw.bootstrap.notify_telegram", side_effect=se("notify")):

            bootstrap(config, gt_root=tmp_path)

        # Verify critical ordering
        assert order.index("kimi") < order.index("install")
        assert order.index("install") < order.index("dolt")
        assert order.index("skills") < order.index("doctor")
        assert order.index("doctor") < order.index("daemon")
        assert order.index("dolt") < order.index("daemon")
        assert order.index("daemon") < order.index("mayor")
        assert order.index("mayor") < order.index("notify")

    def test_error_propagation(self, config, tmp_path):
        with patch("gasclaw.bootstrap.setup_kimi_accounts", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError, match="boom"):
                bootstrap(config, gt_root=tmp_path)


class TestMonitorLoop:
    def test_runs_health_check(self, config, monkeypatch):
        check_count = 0

        def mock_check(**kw):
            nonlocal check_count
            check_count += 1
            if check_count >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport
            return HealthReport(
                dolt="healthy", daemon="healthy", mayor="healthy",
                openclaw="healthy", agents=["mayor"],
                activity={"compliant": True, "last_commit_age": 100},
            )

        activity_return = {"compliant": True, "last_commit_age": 100}
        with patch("gasclaw.bootstrap.check_health", side_effect=mock_check), \
             patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return), \
             patch("gasclaw.bootstrap.notify_telegram"), \
             patch("time.sleep"):
            monitor_loop(config, interval=1)

        assert check_count >= 1

    def test_passes_project_dir_to_activity_check(self, config, monkeypatch):
        """monitor_loop should pass config.project_dir to check_agent_activity."""
        config.project_dir = "/custom/project"
        call_count = 0

        def mock_check_health(**kw):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport
            return HealthReport(
                dolt="healthy", daemon="healthy", mayor="healthy",
                openclaw="healthy", agents=["mayor"],
                activity={"compliant": True, "last_commit_age": 100},
            )

        with patch("gasclaw.bootstrap.check_health", side_effect=mock_check_health), \
             patch("gasclaw.bootstrap.check_agent_activity") as m_activity, \
             patch("gasclaw.bootstrap.notify_telegram"), \
             patch("time.sleep"):
            m_activity.return_value = {"compliant": True, "last_commit_age": 100}
            monitor_loop(config, interval=1)

        m_activity.assert_called_with(
            project_dir="/custom/project",
            deadline_seconds=config.activity_deadline,
        )

    def test_notifies_on_non_compliance(self, config, monkeypatch):
        """monitor_loop sends notification when activity is non-compliant."""
        check_count = 0
        notify_calls = []

        def mock_check(**kw):
            nonlocal check_count
            check_count += 1
            if check_count >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport
            return HealthReport(
                dolt="healthy", daemon="healthy", mayor="healthy",
                openclaw="healthy", agents=["mayor"],
            )

        activity_return = {"compliant": False, "last_commit_age": 7200}
        with patch("gasclaw.bootstrap.check_health", side_effect=mock_check), \
             patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return), \
             patch("gasclaw.bootstrap.notify_telegram") as m_notify, \
             patch("time.sleep"):
            m_notify.side_effect = lambda msg: notify_calls.append(msg)
            monitor_loop(config, interval=1)

        assert len(notify_calls) >= 1
        assert any("ACTIVITY ALERT" in msg for msg in notify_calls)

    def test_notifies_on_service_down(self, config, monkeypatch):
        """monitor_loop sends notification when critical service is down."""
        check_count = 0
        notify_calls = []

        def mock_check(**kw):
            nonlocal check_count
            check_count += 1
            if check_count >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport
            return HealthReport(
                dolt="unhealthy", daemon="healthy", mayor="healthy",
                openclaw="healthy", agents=["mayor"],
            )

        activity_return = {"compliant": True, "last_commit_age": 100}
        with patch("gasclaw.bootstrap.check_health", side_effect=mock_check), \
             patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return), \
             patch("gasclaw.bootstrap.notify_telegram") as m_notify, \
             patch("time.sleep"):
            m_notify.side_effect = lambda msg: notify_calls.append(msg)
            monitor_loop(config, interval=1)

        assert len(notify_calls) >= 1
        assert any("SERVICE DOWN" in msg for msg in notify_calls)
