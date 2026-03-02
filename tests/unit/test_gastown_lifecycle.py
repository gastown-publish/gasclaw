"""Tests for gasclaw.gastown.lifecycle."""

from __future__ import annotations

import subprocess

import pytest

from gasclaw.gastown.lifecycle import start_daemon, start_dolt, start_mayor, stop_all


class TestStartDolt:
    def test_runs_dolt_sql_server(self, monkeypatch):
        calls = []

        class MockProc:
            pid = 1

            def poll(self):
                return None  # Still running

        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: (calls.append((a, kw)), MockProc())[-1],
        )
        monkeypatch.setattr(
            subprocess,
            "run",
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

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: DeadProcess())
        with pytest.raises(RuntimeError, match="exited early"):
            start_dolt(data_dir="/tmp/dolt-data", port=3307, timeout=1)

    def test_raises_timeout_if_never_ready(self, monkeypatch):
        """If dolt never becomes ready, raise TimeoutError."""

        class MockProc:
            pid = 1

            def poll(self):
                return None  # Still running

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MockProc())
        # Always return non-zero (not ready)
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"not ready"),
        )
        with pytest.raises(TimeoutError) as exc_info:
            start_dolt(data_dir="/tmp/dolt-data", port=3307, timeout=1)
        assert "not ready" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()

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

    def test_terminates_on_early_exit(self, monkeypatch):
        """Subprocess is terminated when dolt exits early."""
        terminate_called = []
        wait_called = []

        class DeadProcess:
            pid = 1
            returncode = 1

            def poll(self):
                return self.returncode

            def terminate(self):
                terminate_called.append(True)

            def wait(self, timeout=None):
                wait_called.append(timeout)
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: DeadProcess())
        with pytest.raises(RuntimeError):
            start_dolt(data_dir="/tmp/dolt", port=3307, timeout=1)

        assert len(terminate_called) == 1
        assert len(wait_called) == 1

    def test_terminates_on_timeout(self, monkeypatch):
        """Subprocess is terminated when timeout occurs."""
        terminate_called = []

        class SlowProc:
            pid = 1

            def poll(self):
                return None  # Never exits

            def terminate(self):
                terminate_called.append(True)

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: SlowProc())
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"not ready"),
        )

        with pytest.raises(TimeoutError):
            start_dolt(data_dir="/tmp/dolt", port=3307, timeout=1)

        assert len(terminate_called) == 1

    def test_force_kill_on_terminate_timeout(self, monkeypatch):
        """Process is killed if graceful terminate doesn't work."""
        terminate_called = []
        kill_called = []

        class StubbornProc:
            pid = 1

            def poll(self):
                return None

            def terminate(self):
                terminate_called.append(True)

            def kill(self):
                kill_called.append(True)

            def wait(self, timeout=None):
                if timeout == 5:
                    raise subprocess.TimeoutExpired(cmd=["dolt"], timeout=5)
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: StubbornProc())
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"not ready"),
        )

        with pytest.raises(TimeoutError):
            start_dolt(data_dir="/tmp/dolt", port=3307, timeout=1)

        assert len(terminate_called) == 1
        assert len(kill_called) == 1


class TestStartDaemon:
    def test_runs_gt_daemon(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        start_daemon()
        assert any("daemon" in str(cmd) for cmd in calls)

    def test_handles_failure(self, monkeypatch):
        """start_daemon raises RuntimeError if daemon fails to start."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("daemon failed")),
        )
        with pytest.raises(RuntimeError) as exc_info:
            start_daemon()
        assert "daemon" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    def test_handles_missing_binary(self, monkeypatch):
        """start_daemon raises FileNotFoundError if gt not installed."""

        def raise_not_found(*a, **kw):
            raise FileNotFoundError("gt not found")

        monkeypatch.setattr(subprocess, "run", raise_not_found)
        with pytest.raises(FileNotFoundError):
            start_daemon()


class TestStartMayor:
    def test_runs_gt_mayor_start(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        start_mayor(agent="kimi-claude")
        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        assert any("mayor" in s and "start" in s for s in cmd_strs)
        assert any("kimi-claude" in s for s in cmd_strs)

    def test_handles_failure(self, monkeypatch):
        """start_mayor raises RuntimeError if mayor fails to start."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("mayor failed")),
        )
        with pytest.raises(RuntimeError) as exc_info:
            start_mayor(agent="kimi-claude")
        assert "mayor" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    def test_handles_missing_binary(self, monkeypatch):
        """start_mayor raises FileNotFoundError if gt not installed."""

        def raise_not_found(*a, **kw):
            raise FileNotFoundError("gt not found")

        monkeypatch.setattr(subprocess, "run", raise_not_found)
        with pytest.raises(FileNotFoundError):
            start_mayor(agent="kimi-claude")


class TestStopAll:
    def test_stops_mayor_daemon_dolt(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
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

    def test_handles_oserror_gracefully(self, monkeypatch):
        """stop_all handles OSError (e.g., permission denied) gracefully."""

        def mock_run(*a, **kw):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", mock_run)
        # Should not raise even though we get permission denied
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
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        stop_all()

        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        # Verify exact stop commands
        assert any("mayor" in s and "stop" in s for s in cmd_strs)
        assert any("daemon" in s and "stop" in s for s in cmd_strs)
        assert any("sql-server" in s and "--stop" in s for s in cmd_strs)


class TestStopAllExceptionHandling:
    """Tests for stop_all() exception handling - Issue #68."""

    def test_all_commands_attempted_on_failure(self, monkeypatch):
        """All stop commands are attempted even if one fails."""
        calls = []

        def mock_run(cmd, **kw):
            calls.append((cmd, kw))
            # First command succeeds, others fail
            if "mayor" in cmd:
                raise RuntimeError("mayor stop failed")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        stop_all()

        # All three commands should have been attempted
        assert len(calls) == 3
        assert ["gt", "mayor", "stop"] in [c[0] for c in calls]
        assert ["gt", "daemon", "stop"] in [c[0] for c in calls]
        assert ["dolt", "sql-server", "--stop"] in [c[0] for c in calls]

    def test_file_not_found_error_handled(self, monkeypatch, caplog):
        """FileNotFoundError is handled gracefully."""
        import logging

        def mock_run(cmd, **kw):
            raise FileNotFoundError("command not found")

        monkeypatch.setattr(subprocess, "run", mock_run)

        with caplog.at_level(logging.DEBUG):
            stop_all()

        # Should complete without raising
        assert "Command not found" in caplog.text

    def test_timeout_expired_handled(self, monkeypatch, caplog):
        """TimeoutExpired is handled gracefully."""
        import logging

        def mock_run(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=30)

        monkeypatch.setattr(subprocess, "run", mock_run)

        with caplog.at_level(logging.WARNING):
            stop_all()

        # Should complete without raising
        assert "Timeout stopping service" in caplog.text

    def test_permission_error_handled(self, monkeypatch, caplog):
        """PermissionError (OSError) is handled gracefully."""
        import logging

        def mock_run(cmd, **kw):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", mock_run)

        with caplog.at_level(logging.WARNING):
            stop_all()

        # Should complete without raising
        assert "Error stopping service" in caplog.text

    def test_runtime_error_handled(self, monkeypatch, caplog):
        """RuntimeError is handled gracefully."""
        import logging

        def mock_run(cmd, **kw):
            raise RuntimeError("unexpected error")

        monkeypatch.setattr(subprocess, "run", mock_run)

        with caplog.at_level(logging.WARNING):
            stop_all()

        # Should complete without raising
        assert "Error stopping service" in caplog.text

    def test_all_commands_run_with_timeout(self, monkeypatch):
        """All commands are run with 30 second timeout."""
        calls = []

        def mock_run(cmd, **kw):
            calls.append((cmd, kw))
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        stop_all()

        # Check all commands have timeout=30
        for _, kw in calls:
            assert kw.get("timeout") == 30
            assert kw.get("check") is False

    def test_partial_failure_continues(self, monkeypatch):
        """If one command fails, subsequent commands still run."""
        calls = []

        def mock_run(cmd, **kw):
            calls.append((cmd, kw))
            if "daemon" in cmd:
                raise RuntimeError("daemon stop failed")
            return subprocess.CompletedProcess(cmd, 0)

        monkeypatch.setattr(subprocess, "run", mock_run)

        stop_all()

        # All three commands should have been attempted
        assert len(calls) == 3
        # Check order: mayor, daemon, dolt
        assert "mayor" in calls[0][0]
        assert "daemon" in calls[1][0]
        assert "dolt" in calls[2][0]
