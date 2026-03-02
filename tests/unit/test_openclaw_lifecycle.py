"""Tests for gasclaw.openclaw.lifecycle."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import httpx
import pytest

from gasclaw.openclaw.lifecycle import start_openclaw, stop_openclaw


class TestStartOpenclaw:
    """Tests for start_openclaw function."""

    def test_starts_gateway_process(self, tmp_path):
        """Should start openclaw gateway as subprocess."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # Process still running

        with (
            patch("subprocess.Popen", return_value=mock_proc) as m_popen,
            patch("httpx.get") as m_get,
        ):
            m_get.return_value.status_code = 200  # Health check succeeds
            start_openclaw(port=18789)

            m_popen.assert_called_once_with(
                ["openclaw", "gateway", "start", "--port", "18789"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    def test_waits_for_health_check(self):
        """Should wait until health endpoint returns 200."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("httpx.get") as m_get,
            patch("time.sleep") as m_sleep,
        ):
            # First call fails, second succeeds
            m_get.side_effect = [
                httpx.ConnectError("Connection refused"),
                MagicMock(status_code=200),
            ]
            start_openclaw(port=18789)

            assert m_get.call_count == 2
            m_sleep.assert_called()

    def test_raises_on_early_exit(self):
        """Should raise RuntimeError if process exits early."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # Process exited with error
        mock_proc.returncode = 1

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            pytest.raises(RuntimeError, match="exited early"),
        ):
            start_openclaw(port=18789)

    def test_raises_on_timeout(self):
        """Should raise TimeoutError if health check never passes."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("httpx.get", side_effect=httpx.ConnectError("refused")),
            patch("time.sleep"),  # Don't actually sleep in tests
            pytest.raises(TimeoutError, match="not ready after"),
        ):
            start_openclaw(port=18789, timeout=1)

    def test_cleans_up_subprocess_on_failure(self):
        """Should terminate subprocess if startup fails."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("httpx.get", side_effect=httpx.ConnectError("refused")),
            patch("time.sleep"),
            pytest.raises(TimeoutError),
        ):
            start_openclaw(port=18789, timeout=1)

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once()

    def test_kills_if_terminate_times_out(self):
        """Should kill process if terminate doesn't work."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        # wait(timeout=5) raises TimeoutExpired, then wait() after kill returns None
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 5), None]

        with (
            patch("subprocess.Popen", return_value=mock_proc),
            patch("httpx.get", side_effect=httpx.ConnectError("refused")),
            patch("time.sleep"),
            pytest.raises(TimeoutError),
        ):
            # Cleanup exceptions don't propagate - the original TimeoutError does
            start_openclaw(port=18789, timeout=1)

        mock_proc.terminate.assert_called_once()
        mock_proc.kill.assert_called_once()

    def test_uses_custom_port(self):
        """Should use custom port when specified."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None

        with (
            patch("subprocess.Popen", return_value=mock_proc) as m_popen,
            patch("httpx.get") as m_get,
        ):
            m_get.return_value.status_code = 200
            start_openclaw(port=9999)

            assert m_popen.call_args[0][0] == ["openclaw", "gateway", "start", "--port", "9999"]
            m_get.assert_called_with("http://localhost:9999/health", timeout=2)


class TestStopOpenclaw:
    """Tests for stop_openclaw function."""

    def test_runs_stop_command(self):
        """Should run openclaw gateway stop command."""
        with patch("subprocess.run") as m_run:
            stop_openclaw()

            m_run.assert_called_once_with(
                ["openclaw", "gateway", "stop"],
                check=False,
                timeout=30,
            )

    def test_handles_missing_binary(self):
        """Should handle FileNotFoundError gracefully."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            # Should not raise
            stop_openclaw()

    def test_handles_timeout(self):
        """Should handle timeout gracefully."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            # Should not raise
            stop_openclaw()

    def test_handles_other_errors(self):
        """Should handle other errors gracefully."""
        with patch("subprocess.run", side_effect=OSError("some error")):
            # Should not raise
            stop_openclaw()

    def test_uses_custom_timeout(self):
        """Should use custom timeout when specified."""
        with patch("subprocess.run") as m_run:
            stop_openclaw(timeout=60)

            assert m_run.call_args[1]["timeout"] == 60
