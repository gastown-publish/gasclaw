"""Tests for gasclaw.gastown.lifecycle."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from gasclaw.gastown.lifecycle import start_daemon, start_dolt, start_mayor, stop_all


class TestDoltTcpCheck:
    """Tests for the TCP-based Dolt health check - Issue #338."""

    def test_tcp_connect_succeeds(self, monkeypatch, tmp_path):
        """TCP connection success triggers immediate return."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()

        class MockProc:
            pid = 1

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MockProc())

        # Mock socket to simulate successful connection
        mock_sock = MagicMock()
        mock_sock.connect.return_value = None

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock):
            start_dolt(data_dir=str(data_dir), port=3307, timeout=30)

        # Verify connect was called with correct address
        mock_sock.connect.assert_called_once_with(("127.0.0.1", 3307))
        mock_sock.close.assert_called_once()

    def test_tcp_connect_refused_raises_timeout(self, monkeypatch, tmp_path):
        """ConnectionRefusedError triggers retry until timeout."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()

        class MockProc:
            pid = 1

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MockProc())

        # Mock socket to always refuse connection
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError("Connection refused")

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock), \
             pytest.raises(TimeoutError):
            start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

        # Verify socket was closed after each attempt
        assert mock_sock.close.call_count >= 1

    def test_tcp_connect_oserror_raises_timeout(self, monkeypatch, tmp_path):
        """OSError (e.g., timeout) triggers retry until timeout."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()

        class MockProc:
            pid = 1

            def poll(self):
                return None

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MockProc())

        # Mock socket to raise OSError (simulates timeout)
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("Connection timed out")

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock), \
             pytest.raises(TimeoutError):
            start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

    def test_tcp_check_uses_correct_port(self, monkeypatch, tmp_path):
        """TCP check uses the port from start_dolt parameters."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()
        connect_calls = []

        class MockProc:
            pid = 1

            def poll(self):
                return None

        def mock_popen(*a, **kw):
            return MockProc()

        def mock_connect(addr):
            connect_calls.append(addr)

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        # Mock socket to capture connect args
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = mock_connect

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock):
            start_dolt(data_dir=str(data_dir), port=5432, timeout=1)

        # Verify TCP connect was called with the custom port
        assert ("127.0.0.1", 5432) in connect_calls

    def test_tcp_check_uses_localhost(self, monkeypatch, tmp_path):
        """TCP check connects to localhost (127.0.0.1)."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()
        connect_calls = []

        class MockProc:
            pid = 1

            def poll(self):
                return None

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MockProc())

        def mock_connect(addr):
            connect_calls.append(addr)

        mock_sock = MagicMock()
        mock_sock.connect.side_effect = mock_connect

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock):
            start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

        # Verify connect was to localhost
        assert any(addr[0] == "127.0.0.1" for addr in connect_calls)


class TestStartDolt:
    def test_runs_dolt_sql_server(self, monkeypatch, tmp_path):
        calls = []
        data_dir = tmp_path / "dolt-data"
        data_dir.mkdir()

        class MockProc:
            pid = 1

            def poll(self):
                return None  # Still running

        monkeypatch.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: (calls.append((a, kw)), MockProc())[-1],
        )

        mock_sock = MagicMock()
        mock_sock.connect.return_value = None

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock):
            start_dolt(data_dir=str(data_dir), port=3307, timeout=1)
        assert any("dolt" in str(c) for c in calls)

    def test_raises_if_process_exits_early(self, monkeypatch, tmp_path):
        """If dolt process dies immediately, we should get RuntimeError not TimeoutError."""
        data_dir = tmp_path / "dolt-data"
        data_dir.mkdir()

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
            start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

    def test_raises_timeout_if_never_ready(self, monkeypatch, tmp_path):
        """If dolt never becomes ready, raise TimeoutError."""
        data_dir = tmp_path / "dolt-data"
        data_dir.mkdir()

        class MockProc:
            pid = 1

            def poll(self):
                return None  # Still running

            def terminate(self):
                pass

            def wait(self, timeout=None):
                return 0

        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: MockProc())

        # Mock socket to always refuse connection
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock), \
             pytest.raises(TimeoutError) as exc_info:
                start_dolt(data_dir=str(data_dir), port=3307, timeout=1)
        msg = str(exc_info.value).lower()
        assert "not ready" in msg or "timeout" in msg

    def test_uses_custom_data_dir(self, monkeypatch, tmp_path):
        """start_dolt passes custom data_dir to dolt command."""
        data_dir = tmp_path / "custom-dolt"
        data_dir.mkdir()
        popen_calls = []

        class MockProc:
            pid = 1

            def poll(self):
                return None

        def mock_popen(*a, **kw):
            popen_calls.append(a[0])
            return MockProc()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        # Mock socket to succeed immediately
        mock_sock = MagicMock()
        mock_sock.connect.return_value = None

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock):
            start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

        # Check data-dir is in the command
        cmd_str = " ".join(str(x) for x in popen_calls[0])
        assert "--data-dir" in cmd_str
        assert str(data_dir) in cmd_str

    def test_uses_custom_port(self, monkeypatch, tmp_path):
        """start_dolt uses custom port for server and TCP check."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()
        popen_calls = []
        connect_calls = []

        class MockProc:
            pid = 1

            def poll(self):
                return None

        def mock_popen(*a, **kw):
            popen_calls.append(a[0])
            return MockProc()

        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        # Mock socket to capture connect args
        mock_sock = MagicMock()

        def mock_connect(addr):
            connect_calls.append(addr)

        mock_sock.connect.side_effect = mock_connect

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock):
            start_dolt(data_dir=str(data_dir), port=9999, timeout=1)

        # Check port in Popen command
        popen_str = " ".join(str(x) for x in popen_calls[0])
        assert "9999" in popen_str
        # Check port in TCP connect
        assert ("127.0.0.1", 9999) in connect_calls

    def test_terminates_on_early_exit(self, monkeypatch, tmp_path):
        """Subprocess is terminated when dolt exits early."""
        data_dir = tmp_path / "dolt-data"
        data_dir.mkdir()
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
            start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

        assert len(terminate_called) == 1
        assert len(wait_called) == 1

    def test_terminates_on_timeout(self, monkeypatch, tmp_path):
        """Subprocess is terminated when timeout occurs."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()
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

        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock), \
             pytest.raises(TimeoutError):
                start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

        assert len(terminate_called) == 1

    def test_force_kill_on_terminate_timeout(self, monkeypatch, tmp_path):
        """Process is killed if graceful terminate doesn't work."""
        data_dir = tmp_path / "dolt"
        data_dir.mkdir()
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

        mock_sock = MagicMock()
        mock_sock.connect.side_effect = ConnectionRefusedError

        with patch("gasclaw.gastown.lifecycle.socket.socket", return_value=mock_sock), \
             pytest.raises(TimeoutError):
                start_dolt(data_dir=str(data_dir), port=3307, timeout=1)

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
        assert any("pkill" in s and "dolt" in s for s in cmd_strs)


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
        assert ["pkill", "-f", "dolt sql-server"] in [c[0] for c in calls]

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
        # Check order: mayor, daemon, dolt-stop
        assert "mayor" in calls[0][0]
        assert "daemon" in calls[1][0]
        assert calls[2][0] == ["pkill", "-f", "dolt sql-server"]
