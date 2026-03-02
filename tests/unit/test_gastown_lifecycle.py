"""Tests for gasclaw.gastown.lifecycle."""

from __future__ import annotations

import subprocess

from gasclaw.gastown.lifecycle import start_dolt, start_daemon, start_mayor, stop_all


class TestStartDolt:
    def test_runs_dolt_sql_server(self, monkeypatch):
        calls = []

        class MockProc:
            pid = 1
            def poll(self):
                return None  # Still running

        monkeypatch.setattr(
            subprocess, "Popen",
            lambda *a, **kw: (calls.append((a, kw)), MockProc())[-1],
        )
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b""),
        )
        start_dolt(data_dir="/tmp/dolt-data", port=3307, timeout=1)
        assert any("dolt" in str(c) for c in calls)

    def test_raises_if_process_exits_early(self, monkeypatch):
        """If dolt process dies immediately, we should get RuntimeError not TimeoutError."""
        class DeadProcess:
            pid = 1
            returncode = 1
            def poll(self):
                return self.returncode  # Process already exited

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: DeadProcess())
        try:
            start_dolt(data_dir="/tmp/dolt-data", port=3307, timeout=1)
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "exited early" in str(e)
            assert "1" in str(e)


class TestStartDaemon:
    def test_runs_gt_daemon(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        start_daemon()
        assert any("daemon" in str(cmd) for cmd in calls)


class TestStartMayor:
    def test_runs_gt_mayor_start(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        start_mayor(agent="kimi-claude")
        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        assert any("mayor" in s and "start" in s for s in cmd_strs)
        assert any("kimi-claude" in s for s in cmd_strs)


class TestStopAll:
    def test_stops_mayor_daemon_dolt(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        stop_all()
        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        assert any("mayor" in s and "stop" in s for s in cmd_strs)
        assert any("daemon" in s and "stop" in s for s in cmd_strs)
