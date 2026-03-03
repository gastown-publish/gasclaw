"""Tests for gateway watchdog module."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

# Load watchdog module from maintainer/scripts
_scripts_path = Path(__file__).parent.parent.parent / "maintainer" / "scripts"
_spec = importlib.util.spec_from_file_location(
    "gateway_watchdog", _scripts_path / "gateway-watchdog.py"
)
_gateway_watchdog = importlib.util.module_from_spec(_spec)
sys.modules["gateway_watchdog"] = _gateway_watchdog
_spec.loader.exec_module(_gateway_watchdog)

GatewayWatchdog = _gateway_watchdog.GatewayWatchdog
main = _gateway_watchdog.main
send_telegram_notification = _gateway_watchdog.send_telegram_notification


class TestGatewayWatchdog:
    """Test GatewayWatchdog class."""

    def test_load_state_creates_default(self, tmp_path):
        """Watchdog creates default state when file doesn't exist."""
        state_file = tmp_path / "state.json"
        watchdog = GatewayWatchdog(state_file=str(state_file))

        state = watchdog._load_state()

        assert state["last_message_timestamp"] is None
        assert state["restart_count"] == 0
        assert state["last_restart_timestamp"] is None

    def test_load_state_reads_existing(self, tmp_path):
        """Watchdog reads existing state file."""
        state_file = tmp_path / "state.json"
        existing = {
            "last_message_timestamp": 12345.0,
            "restart_count": 5,
            "last_restart_timestamp": 67890.0,
        }
        state_file.write_text(json.dumps(existing))

        watchdog = GatewayWatchdog(state_file=str(state_file))
        state = watchdog._load_state()

        assert state["last_message_timestamp"] == 12345.0
        assert state["restart_count"] == 5

    def test_save_state_writes_file(self, tmp_path):
        """Watchdog saves state to file."""
        state_file = tmp_path / "state.json"
        watchdog = GatewayWatchdog(state_file=str(state_file))
        watchdog._state = {
            "last_message_timestamp": 11111.0,
            "restart_count": 3,
        }

        watchdog._save_state()

        saved = json.loads(state_file.read_text())
        assert saved["last_message_timestamp"] == 11111.0
        assert saved["restart_count"] == 3

    def test_check_for_new_messages_detects_telegram_update(self, tmp_path):
        """Watchdog detects telegram update in log."""
        log_file = tmp_path / "gateway.log"
        log_file.write_text("Some initial log\n")

        watchdog = GatewayWatchdog(
            state_file=str(tmp_path / "state.json"),
            gateway_log=str(log_file),
        )
        watchdog._last_log_position = 0

        # First check - no new messages
        result1 = watchdog._check_for_new_messages()
        assert result1 is False

        # Simulate new message
        log_file.write_text("Some initial log\nReceived telegram update: {...}\n")

        result2 = watchdog._check_for_new_messages()
        assert result2 is True

    def test_check_for_new_messages_handles_missing_file(self, tmp_path):
        """Watchdog handles missing log file gracefully."""
        watchdog = GatewayWatchdog(
            state_file=str(tmp_path / "state.json"),
            gateway_log=str(tmp_path / "nonexistent.log"),
        )

        result = watchdog._check_for_new_messages()
        assert result is False

    def test_is_stale_when_no_messages_and_no_restart(self, tmp_path):
        """Watchdog not stale when just started."""
        watchdog = GatewayWatchdog(
            state_file=str(tmp_path / "state.json"),
            stale_threshold=300,
        )
        watchdog._state = {
            "last_message_timestamp": None,
            "last_restart_timestamp": None,
        }

        assert watchdog._is_stale() is False

    def test_is_stale_when_no_messages_long_after_restart(self, tmp_path):
        """Watchdog stale when no messages after threshold."""
        watchdog = GatewayWatchdog(
            state_file=str(tmp_path / "state.json"),
            stale_threshold=300,
        )
        watchdog._state = {
            "last_message_timestamp": None,
            "last_restart_timestamp": time.time() - 400,  # 400s ago
        }

        assert watchdog._is_stale() is True

    def test_is_stale_when_old_message(self, tmp_path):
        """Watchdog stale when last message is old."""
        watchdog = GatewayWatchdog(
            state_file=str(tmp_path / "state.json"),
            stale_threshold=300,
        )
        watchdog._state = {
            "last_message_timestamp": time.time() - 400,  # 400s ago
        }

        assert watchdog._is_stale() is True

    def test_is_not_stale_when_recent_message(self, tmp_path):
        """Watchdog not stale when recent message exists."""
        watchdog = GatewayWatchdog(
            state_file=str(tmp_path / "state.json"),
            stale_threshold=300,
        )
        watchdog._state = {
            "last_message_timestamp": time.time() - 60,  # 60s ago
        }

        assert watchdog._is_stale() is False

    def test_check_gateway_health_with_running_process(self, tmp_path):
        """Watchdog detects running gateway process."""
        pid_file = tmp_path / "gateway.pid"
        pid_file.write_text("12345")

        watchdog = GatewayWatchdog(state_file=str(tmp_path / "state.json"))

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="12345"),
            patch("os.kill") as mock_kill,
        ):
            mock_kill.return_value = None  # Process exists
            assert watchdog._check_gateway_health() is True

    def test_check_gateway_health_with_dead_process(self, tmp_path):
        """Watchdog detects dead gateway process."""
        pid_file = tmp_path / "gateway.pid"
        pid_file.write_text("99999")

        watchdog = GatewayWatchdog(state_file=str(tmp_path / "state.json"))

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value="99999"),
            patch("os.kill", side_effect=ProcessLookupError),
        ):
            assert watchdog._check_gateway_health() is False

    def test_run_cycle_updates_timestamp_on_new_message(self, tmp_path):
        """Watchdog cycle updates timestamp when message found."""
        log_file = tmp_path / "gateway.log"
        state_file = tmp_path / "state.json"
        log_file.write_text("telegram update received\n")

        watchdog = GatewayWatchdog(
            state_file=str(state_file),
            gateway_log=str(log_file),
        )

        with patch.object(watchdog, "_check_gateway_health", return_value=True):
            watchdog.run_cycle()

        assert watchdog._state["last_message_timestamp"] is not None

    def test_run_cycle_restarts_when_stale(self, tmp_path):
        """Watchdog restarts gateway when stale."""
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "last_message_timestamp": time.time() - 400,
            "restart_count": 0,
        }))

        watchdog = GatewayWatchdog(
            state_file=str(state_file),
            stale_threshold=300,
        )

        with (
            patch.object(watchdog, "_check_gateway_health", return_value=True),
            patch.object(watchdog, "_check_for_new_messages", return_value=False),
            patch.object(watchdog, "_restart_gateway", return_value=True) as mock_restart,
        ):
            watchdog.run_cycle()

            mock_restart.assert_called_once()


class TestSendTelegramNotification:
    """Test send_telegram_notification function."""

    def test_sends_notification_with_valid_env(self, monkeypatch):
        """Notification sent when env vars are set."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"ok": true}'
            send_telegram_notification("Test message")

            mock_urlopen.assert_called_once()

    def test_skips_when_no_token(self, monkeypatch):
        """No notification when token missing."""
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        with patch("urllib.request.urlopen") as mock_urlopen:
            send_telegram_notification("Test message")
            mock_urlopen.assert_not_called()

    def test_handles_errors_gracefully(self, monkeypatch):
        """Errors are handled gracefully."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

        with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            # Should not raise
            send_telegram_notification("Test message")


class TestMain:
    """Test main entry point."""

    def test_main_runs_watchdog(self):
        """Main function runs watchdog."""
        with patch.object(GatewayWatchdog, "run") as mock_run:
            with patch("sys.argv", ["gateway-watchdog", "--verbose"]):
                result = main()

            assert result == 0
            mock_run.assert_called_once()

    def test_main_handles_keyboard_interrupt(self):
        """Main handles keyboard interrupt gracefully."""
        with patch.object(GatewayWatchdog, "run", side_effect=KeyboardInterrupt):
            with patch("sys.argv", ["gateway-watchdog"]):
                result = main()

            assert result == 0

    def test_main_daemon_mode_forks(self):
        """Daemon mode forks process."""
        with patch("os.fork", return_value=1234):
            with patch("sys.argv", ["gateway-watchdog", "--daemon"]):
                result = main()

            # Parent exits with 0 after fork
            assert result == 0
