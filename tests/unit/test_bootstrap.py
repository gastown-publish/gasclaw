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
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: type("P", (), {"pid": 1, "poll": lambda s: None})(),
        )

        from gasclaw.openclaw.doctor import DoctorResult

        mock_doctor = DoctorResult(healthy=True, returncode=0, output="OK")

        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts") as m_kimi,
            patch("gasclaw.bootstrap.write_agent_config") as m_agent,
            patch("gasclaw.bootstrap.gastown_install") as m_install,
            patch("gasclaw.bootstrap.start_dolt") as m_dolt,
            patch("gasclaw.bootstrap.write_openclaw_config") as m_oc,
            patch("gasclaw.bootstrap.install_skills") as m_skills,
            patch("gasclaw.bootstrap.run_doctor", return_value=mock_doctor) as m_doctor,
            patch("gasclaw.bootstrap.start_daemon") as m_daemon,
            patch("gasclaw.bootstrap.start_mayor") as m_mayor,
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
        ):
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

        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts", side_effect=se("kimi")),
            patch("gasclaw.bootstrap.write_agent_config", side_effect=se("agent_config")),
            patch("gasclaw.bootstrap.gastown_install", side_effect=se("install")),
            patch("gasclaw.bootstrap.start_dolt", side_effect=se("dolt")),
            patch("gasclaw.bootstrap.write_openclaw_config", side_effect=se("openclaw")),
            patch("gasclaw.bootstrap.install_skills", side_effect=se("skills")),
            patch("gasclaw.bootstrap.run_doctor", side_effect=doctor_side_effect),
            patch("gasclaw.bootstrap.start_daemon", side_effect=se("daemon")),
            patch("gasclaw.bootstrap.start_mayor", side_effect=se("mayor")),
            patch("gasclaw.bootstrap.notify_telegram", side_effect=se("notify")),
        ):
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
        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            bootstrap(config, gt_root=tmp_path)

    def test_rollback_on_dolt_failure(self, config, tmp_path):
        """Rollback stops dolt if it was started before failure."""
        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts"),
            patch("gasclaw.bootstrap.write_agent_config"),
            patch("gasclaw.bootstrap.gastown_install"),
            patch("gasclaw.bootstrap.start_dolt") as m_dolt,
            patch("gasclaw.bootstrap.stop_all") as m_stop,
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
        ):
            m_dolt.side_effect = RuntimeError("dolt failed")

            with pytest.raises(RuntimeError, match="dolt failed"):
                bootstrap(config, gt_root=tmp_path)

            # Should not call stop_all since dolt failed to start
            m_stop.assert_not_called()
            # Should notify of failure
            assert any("failed" in str(call).lower() for call in m_notify.call_args_list)

    def test_rollback_on_daemon_failure(self, config, tmp_path):
        """Rollback stops all services if daemon fails to start."""
        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts"),
            patch("gasclaw.bootstrap.write_agent_config"),
            patch("gasclaw.bootstrap.gastown_install"),
            patch("gasclaw.bootstrap.start_dolt"),
            patch("gasclaw.bootstrap.write_openclaw_config"),
            patch("gasclaw.bootstrap.install_skills"),
            patch("gasclaw.bootstrap.run_doctor") as m_doctor,
            patch("gasclaw.bootstrap.start_daemon") as m_daemon,
            patch("gasclaw.bootstrap.stop_all") as m_stop,
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
        ):
            from gasclaw.openclaw.doctor import DoctorResult

            m_doctor.return_value = DoctorResult(healthy=True, returncode=0, output="OK")
            m_daemon.side_effect = RuntimeError("daemon failed")

            with pytest.raises(RuntimeError, match="daemon failed"):
                bootstrap(config, gt_root=tmp_path)

            # Should call stop_all to rollback
            m_stop.assert_called_once()
            # Should notify of failure and rollback
            notify_calls = [str(call) for call in m_notify.call_args_list]
            assert any("failed" in c.lower() for c in notify_calls)
            assert any("rolling back" in c.lower() for c in notify_calls)

    def test_rollback_on_mayor_failure(self, config, tmp_path):
        """Rollback stops all services if mayor fails to start."""
        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts"),
            patch("gasclaw.bootstrap.write_agent_config"),
            patch("gasclaw.bootstrap.gastown_install"),
            patch("gasclaw.bootstrap.start_dolt"),
            patch("gasclaw.bootstrap.write_openclaw_config"),
            patch("gasclaw.bootstrap.install_skills"),
            patch("gasclaw.bootstrap.run_doctor") as m_doctor,
            patch("gasclaw.bootstrap.start_daemon"),
            patch("gasclaw.bootstrap.start_mayor") as m_mayor,
            patch("gasclaw.bootstrap.stop_all") as m_stop,
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
        ):
            from gasclaw.openclaw.doctor import DoctorResult

            m_doctor.return_value = DoctorResult(healthy=True, returncode=0, output="OK")
            m_mayor.side_effect = RuntimeError("mayor failed")

            with pytest.raises(RuntimeError, match="mayor failed"):
                bootstrap(config, gt_root=tmp_path)

            # Should call stop_all to rollback
            m_stop.assert_called_once()
            # Should notify of failure and rollback
            notify_calls = [str(call) for call in m_notify.call_args_list]
            assert any("failed" in c.lower() for c in notify_calls)

    def test_rollback_error_handled(self, config, tmp_path):
        """Rollback errors are caught and notified but original exception is raised."""
        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts"),
            patch("gasclaw.bootstrap.write_agent_config"),
            patch("gasclaw.bootstrap.gastown_install"),
            patch("gasclaw.bootstrap.start_dolt"),
            patch("gasclaw.bootstrap.write_openclaw_config"),
            patch("gasclaw.bootstrap.install_skills"),
            patch("gasclaw.bootstrap.run_doctor") as m_doctor,
            patch("gasclaw.bootstrap.start_daemon"),
            patch("gasclaw.bootstrap.start_mayor") as m_mayor,
            patch("gasclaw.bootstrap.stop_all") as m_stop,
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
        ):
            from gasclaw.openclaw.doctor import DoctorResult

            m_doctor.return_value = DoctorResult(healthy=True, returncode=0, output="OK")
            m_mayor.side_effect = RuntimeError("mayor failed")
            m_stop.side_effect = RuntimeError("rollback also failed")

            with pytest.raises(RuntimeError, match="mayor failed"):
                bootstrap(config, gt_root=tmp_path)

            # Should still attempt stop_all
            m_stop.assert_called_once()
            # Should notify about rollback error
            notify_calls = [str(call) for call in m_notify.call_args_list]
            assert any("rollback error" in c.lower() for c in notify_calls)


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
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
                activity={"compliant": True, "last_commit_age": 100},
            )

        activity_return = {"compliant": True, "last_commit_age": 100}
        with (
            patch("gasclaw.bootstrap.check_health", side_effect=mock_check),
            patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return),
            patch("gasclaw.bootstrap.notify_telegram"),
            patch("time.sleep"),
        ):
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
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
                activity={"compliant": True, "last_commit_age": 100},
            )

        with (
            patch("gasclaw.bootstrap.check_health", side_effect=mock_check_health),
            patch("gasclaw.bootstrap.check_agent_activity") as m_activity,
            patch("gasclaw.bootstrap.notify_telegram"),
            patch("time.sleep"),
        ):
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
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        activity_return = {"compliant": False, "last_commit_age": 7200}
        with (
            patch("gasclaw.bootstrap.check_health", side_effect=mock_check),
            patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return),
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
            patch("time.sleep"),
        ):
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
                dolt="unhealthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
            )

        activity_return = {"compliant": True, "last_commit_age": 100}
        with (
            patch("gasclaw.bootstrap.check_health", side_effect=mock_check),
            patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return),
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
            patch("time.sleep"),
        ):
            m_notify.side_effect = lambda msg: notify_calls.append(msg)
            monitor_loop(config, interval=1)

        assert len(notify_calls) >= 1
        assert any("SERVICE DOWN" in msg for msg in notify_calls)

    def test_notifies_when_doctor_unhealthy(self, config, monkeypatch, tmp_path):
        """bootstrap notifies when doctor reports unhealthy."""
        notify_calls = []

        from gasclaw.openclaw.doctor import DoctorResult

        mock_doctor = DoctorResult(
            healthy=False, returncode=1, output="Config error: missing token"
        )

        with (
            patch("gasclaw.bootstrap.setup_kimi_accounts"),
            patch("gasclaw.bootstrap.write_agent_config"),
            patch("gasclaw.bootstrap.gastown_install"),
            patch("gasclaw.bootstrap.start_dolt"),
            patch("gasclaw.bootstrap.write_openclaw_config"),
            patch("gasclaw.bootstrap.install_skills"),
            patch("gasclaw.bootstrap.run_doctor", return_value=mock_doctor),
            patch("gasclaw.bootstrap.start_daemon"),
            patch("gasclaw.bootstrap.start_mayor"),
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
        ):
            m_notify.side_effect = lambda msg: notify_calls.append(msg)
            bootstrap(config, gt_root=tmp_path)

        # Should have "Gasclaw is up" and doctor warning notifications
        assert len(notify_calls) >= 1
        assert any("openclaw doctor" in msg.lower() for msg in notify_calls)
        assert any("config error" in msg.lower() for msg in notify_calls)

    def test_notifies_on_multiple_services_down(self, config, monkeypatch):
        """monitor_loop sends notifications for each unhealthy service."""
        check_count = 0
        notify_calls = []

        def mock_check(**kw):
            nonlocal check_count
            check_count += 1
            if check_count >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport

            return HealthReport(
                dolt="unhealthy",
                daemon="unhealthy",
                mayor="unhealthy",
                openclaw="healthy",
                agents=[],
            )

        activity_return = {"compliant": True, "last_commit_age": 100}
        with (
            patch("gasclaw.bootstrap.check_health", side_effect=mock_check),
            patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return),
            patch("gasclaw.bootstrap.notify_telegram") as m_notify,
            patch("time.sleep"),
        ):
            m_notify.side_effect = lambda msg: notify_calls.append(msg)
            monitor_loop(config, interval=1)

        # Should have notifications for dolt, daemon, and mayor
        service_notifications = [msg for msg in notify_calls if "SERVICE DOWN" in msg]
        assert len(service_notifications) >= 3  # dolt, daemon, mayor
        assert any("dolt" in msg for msg in service_notifications)
        assert any("daemon" in msg for msg in service_notifications)
        assert any("mayor" in msg for msg in service_notifications)

    def test_uses_config_interval_when_none_provided(self, config, monkeypatch):
        """monitor_loop uses config.monitor_interval when interval=None."""
        check_count = 0

        def mock_check(**kw):
            nonlocal check_count
            check_count += 1
            if check_count >= 2:
                raise KeyboardInterrupt
            from gasclaw.health import HealthReport

            return HealthReport(
                dolt="healthy",
                daemon="healthy",
                mayor="healthy",
                openclaw="healthy",
                agents=["mayor"],
                activity={"compliant": True, "last_commit_age": 100},
            )

        activity_return = {"compliant": True, "last_commit_age": 100}
        config.monitor_interval = 42  # Custom interval

        with (
            patch("gasclaw.bootstrap.check_health", side_effect=mock_check),
            patch("gasclaw.bootstrap.check_agent_activity", return_value=activity_return),
            patch("gasclaw.bootstrap.notify_telegram"),
            patch("time.sleep") as m_sleep,
        ):
            monitor_loop(config, interval=None)  # interval=None triggers line 131

        # Verify sleep was called with the config interval
        m_sleep.assert_called_with(42)
