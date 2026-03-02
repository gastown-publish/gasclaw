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

    def test_doctor_unhealthy_notification(self, config, monkeypatch, tmp_path):
        """Test that bootstrap notifies when doctor finds issues (line 72)."""
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        monkeypatch.setattr(
            subprocess, "Popen",
            lambda *a, **kw: type("P", (), {"pid": 1, "poll": lambda s: None})(),
        )

        from gasclaw.openclaw.doctor import DoctorResult
        mock_doctor = DoctorResult(healthy=False, returncode=1, output="Config error: invalid key")

        with patch("gasclaw.bootstrap.setup_kimi_accounts"), \
             patch("gasclaw.bootstrap.write_agent_config"), \
             patch("gasclaw.bootstrap.gastown_install"), \
             patch("gasclaw.bootstrap.start_dolt"), \
             patch("gasclaw.bootstrap.write_openclaw_config"), \
             patch("gasclaw.bootstrap.install_skills"), \
             patch("gasclaw.bootstrap.run_doctor", return_value=mock_doctor), \
             patch("gasclaw.bootstrap.start_daemon"), \
             patch("gasclaw.bootstrap.start_mayor"), \
             patch("gasclaw.bootstrap.notify_telegram") as m_notify:

            bootstrap(config, gt_root=tmp_path)

            # Should notify twice: once for doctor issues, once for "up and running"
            assert m_notify.call_count == 2
            # First call should be about doctor issues
            first_call = m_notify.call_args_list[0]
            assert "openclaw doctor found issues" in first_call[0][0]
            assert "Config error" in first_call[0][0]


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
