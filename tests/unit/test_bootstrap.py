"""Tests for gasclaw.bootstrap."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch, call

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

        with patch("gasclaw.bootstrap.setup_kimi_accounts") as m_kimi, \
             patch("gasclaw.bootstrap.write_agent_config") as m_agent, \
             patch("gasclaw.bootstrap.gastown_install") as m_install, \
             patch("gasclaw.bootstrap.start_dolt") as m_dolt, \
             patch("gasclaw.bootstrap.write_openclaw_config") as m_oc, \
             patch("gasclaw.bootstrap.install_skills") as m_skills, \
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
            m_daemon.assert_called_once()
            m_mayor.assert_called_once()
            m_notify.assert_called_once()

    def test_call_order(self, config, monkeypatch, tmp_path):
        order = []

        with patch("gasclaw.bootstrap.setup_kimi_accounts", side_effect=lambda *a, **kw: order.append("kimi")), \
             patch("gasclaw.bootstrap.write_agent_config", side_effect=lambda *a, **kw: order.append("agent_config")), \
             patch("gasclaw.bootstrap.gastown_install", side_effect=lambda *a, **kw: order.append("install")), \
             patch("gasclaw.bootstrap.start_dolt", side_effect=lambda *a, **kw: order.append("dolt")), \
             patch("gasclaw.bootstrap.write_openclaw_config", side_effect=lambda *a, **kw: order.append("openclaw")), \
             patch("gasclaw.bootstrap.install_skills", side_effect=lambda *a, **kw: order.append("skills")), \
             patch("gasclaw.bootstrap.start_daemon", side_effect=lambda *a, **kw: order.append("daemon")), \
             patch("gasclaw.bootstrap.start_mayor", side_effect=lambda *a, **kw: order.append("mayor")), \
             patch("gasclaw.bootstrap.notify_telegram", side_effect=lambda *a, **kw: order.append("notify")):

            bootstrap(config, gt_root=tmp_path)

        # Verify critical ordering
        assert order.index("kimi") < order.index("install")
        assert order.index("install") < order.index("dolt")
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

        with patch("gasclaw.bootstrap.check_health", side_effect=mock_check), \
             patch("gasclaw.bootstrap.check_agent_activity", return_value={"compliant": True, "last_commit_age": 100}), \
             patch("gasclaw.bootstrap.notify_telegram"), \
             patch("time.sleep"):
            monitor_loop(config, interval=1)

        assert check_count >= 1
