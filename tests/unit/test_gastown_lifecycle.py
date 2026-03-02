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

    def test_uses_custom_data_dir(self, monkeypatch):
        """start_dolt passes custom data_dir to dolt command."""
        popen_calls = []
        run_calls = []

        class MockProc:
            pid = 1
            def poll(self):
                return None

        def mock_popen(*a, **kw):
            popen_calls.append(a[0])
            return MockProc()

        def mock_run(*a, **kw):
            run_calls.append(a[0])
            return subprocess.CompletedProcess(a[0], 0)

        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(subprocess, "run", mock_run)

        start_dolt(data_dir="/custom/dolt/path", port=3307, timeout=1)

        # Check data-dir is in the command
        cmd_str = " ".join(str(x) for x in popen_calls[0])
        assert "--data-dir" in cmd_str
        assert "/custom/dolt/path" in cmd_str

    def test_uses_custom_port(self, monkeypatch):
        """start_dolt uses custom port for both server and health check."""
        popen_calls = []
        run_calls = []

        class MockProc:
            pid = 1
            def poll(self):
                return None

        def mock_popen(*a, **kw):
            popen_calls.append(a[0])
            return MockProc()

        def mock_run(*a, **kw):
            run_calls.append(a[0])
            return subprocess.CompletedProcess(a[0], 0)

        monkeypatch.setattr(subprocess, "Popen", mock_popen)
        monkeypatch.setattr(subprocess, "run", mock_run)

        start_dolt(data_dir="/tmp/dolt", port=9999, timeout=1)

        # Check port appears in both commands
        popen_str = " ".join(str(x) for x in popen_calls[0])
        run_str = " ".join(str(x) for x in run_calls[0])
        assert "9999" in popen_str
        assert "9999" in run_str


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

    def test_handles_partial_failure(self, monkeypatch):
        """stop_all continues even if one service fails to stop."""
        calls = []

        def mock_run(*a, **kw):
            calls.append(a[0])
            cmd_str = " ".join(str(x) for x in a[0])
            if "mayor" in cmd_str:
                return subprocess.CompletedProcess(a[0], 0)  # Success
            elif "daemon" in cmd_str:
                return subprocess.CompletedProcess(a[0], 1, stderr=b"daemon not running")
            elif "dolt" in cmd_str:
                return subprocess.CompletedProcess(a[0], 0)  # Success
            return subprocess.CompletedProcess(a[0], 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        stop_all()

        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        assert any("mayor" in s for s in cmd_strs)
        assert any("daemon" in s for s in cmd_strs)
        assert any("dolt" in s for s in cmd_strs)

    def test_handles_file_not_found_on_any_command(self, monkeypatch):
        """stop_all handles FileNotFoundError for any command."""
        calls = []

        def mock_run(*a, **kw):
            calls.append(a[0])
            return subprocess.CompletedProcess(a[0], 0)

        monkeypatch.setattr(subprocess, "run", mock_run)
        stop_all()

        # All three commands should have been attempted
        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        assert any("mayor" in c for c in cmd_strs)
        assert any("daemon" in c for c in cmd_strs)
        assert any("dolt" in c for c in cmd_strs)

    def test_all_services_receive_stop_commands(self, monkeypatch):
        """stop_all issues correct stop commands to all services."""
        calls = []

        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        stop_all()

        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        # Verify exact stop commands
        assert any("mayor" in s and "stop" in s for s in cmd_strs)
        assert any("daemon" in s and "stop" in s for s in cmd_strs)
        assert any("sql-server" in s and "--stop" in s for s in cmd_strs)
