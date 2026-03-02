"""Tests for gasclaw.gastown.lifecycle."""

from __future__ import annotations

import subprocess

from gasclaw.gastown.lifecycle import start_daemon, start_dolt, start_mayor, stop_all


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

    def test_raises_timeout_if_never_ready(self, monkeypatch):
        """If dolt never becomes ready, raise TimeoutError."""
        class MockProc:
            pid = 1
            def poll(self):
                return None  # Still running

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MockProc())
        # Always return non-zero (not ready)
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"not ready"),
        )
        try:
            start_dolt(data_dir="/tmp/dolt-data", port=3307, timeout=1)
            assert False, "Expected TimeoutError"
        except TimeoutError as e:
            assert "not ready" in str(e).lower() or "timeout" in str(e).lower()


class TestStartDaemon:
    def test_runs_gt_daemon(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        start_daemon()
        assert any("daemon" in str(cmd) for cmd in calls)

    def test_handles_failure(self, monkeypatch):
        """start_daemon raises RuntimeError if daemon fails to start."""
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("daemon failed")),
        )
        try:
            start_daemon()
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "daemon" in str(e).lower() or "failed" in str(e).lower()

    def test_handles_missing_binary(self, monkeypatch):
        """start_daemon raises FileNotFoundError if gt not installed."""
        def raise_not_found(*a, **kw):
            raise FileNotFoundError("gt not found")
        monkeypatch.setattr(subprocess, "run", raise_not_found)
        try:
            start_daemon()
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass


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

    def test_handles_failure(self, monkeypatch):
        """start_mayor raises RuntimeError if mayor fails to start."""
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("mayor failed")),
        )
        try:
            start_mayor(agent="kimi-claude")
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "mayor" in str(e).lower() or "failed" in str(e).lower()

    def test_handles_missing_binary(self, monkeypatch):
        """start_mayor raises FileNotFoundError if gt not installed."""
        def raise_not_found(*a, **kw):
            raise FileNotFoundError("gt not found")
        monkeypatch.setattr(subprocess, "run", raise_not_found)
        try:
            start_mayor(agent="kimi-claude")
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass


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

    def test_handles_stop_failures_gracefully(self, monkeypatch):
        """stop_all uses check=False so failures don't raise."""
        def mock_run(*a, **kw):
            # Simulate failure for all commands
            return subprocess.CompletedProcess(a[0], 1, stderr=b"not running")

        monkeypatch.setattr(subprocess, "run", mock_run)
        # Should not raise even though all commands "fail"
        stop_all()

    def test_handles_missing_binaries_gracefully(self, monkeypatch):
        """stop_all handles FileNotFoundError when binaries are missing."""
        def mock_run(*a, **kw):
            raise FileNotFoundError("gt not found")

        monkeypatch.setattr(subprocess, "run", mock_run)
        # Should not raise even though binaries are missing
        stop_all()
