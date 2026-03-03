#!/usr/bin/env python3
"""Gateway watchdog: monitors OpenClaw gateway polling health.

Tracks last-message-received timestamp and restarts gateway if stale.
Addresses issue #272: Gateway polling stability.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


# Default configuration
DEFAULT_STATE_FILE = "/workspace/state/gateway-watchdog.json"
DEFAULT_LOG_FILE = "/workspace/logs/gateway-watchdog.log"
DEFAULT_STALE_THRESHOLD_SECONDS = 300  # 5 minutes
DEFAULT_CHECK_INTERVAL_SECONDS = 60  # 1 minute
DEFAULT_GATEWAY_LOG = "/workspace/logs/openclaw-gateway.log"

logger = logging.getLogger(__name__)


class GatewayWatchdog:
    """Monitors OpenClaw gateway and restarts if polling becomes stale."""

    def __init__(
        self,
        *,
        state_file: str = DEFAULT_STATE_FILE,
        stale_threshold: int = DEFAULT_STALE_THRESHOLD_SECONDS,
        check_interval: int = DEFAULT_CHECK_INTERVAL_SECONDS,
        gateway_log: str = DEFAULT_GATEWAY_LOG,
        notify_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.state_file = Path(state_file)
        self.stale_threshold = stale_threshold
        self.check_interval = check_interval
        self.gateway_log = Path(gateway_log)
        self.notify_callback = notify_callback
        self._running = False
        self._state: dict = {}
        self._last_log_position = 0

    def _load_state(self) -> dict:
        """Load watchdog state from file."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load state: %s", e)
        return {
            "last_message_timestamp": None,
            "restart_count": 0,
            "last_restart_timestamp": None,
        }

    def _save_state(self) -> None:
        """Save watchdog state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(self._state, indent=2))
        except OSError as e:
            logger.warning("Failed to save state: %s", e)

    def _check_for_new_messages(self) -> bool:
        """Check gateway log for new messages, update timestamp if found.

        Returns:
            True if new messages were detected, False otherwise.
        """
        if not self.gateway_log.exists():
            return False

        try:
            with open(self.gateway_log, "r") as f:
                # Seek to last position
                f.seek(self._last_log_position)
                new_content = f.read()
                self._last_log_position = f.tell()

            # Look for telegram update log entries
            # Pattern: "telegram update" or "Received message" in logs
            message_patterns = [
                r"telegram update",
                r"Received message",
                r"Processing update",
                r"telegram.*update",
            ]

            for pattern in message_patterns:
                if re.search(pattern, new_content, re.IGNORECASE):
                    logger.debug("Found message pattern: %s", pattern)
                    return True

            return False
        except OSError as e:
            logger.warning("Error reading gateway log: %s", e)
            return False

    def _is_stale(self) -> bool:
        """Check if gateway polling is stale (no messages for threshold time).

        Returns:
            True if stale and needs restart, False otherwise.
        """
        last_msg = self._state.get("last_message_timestamp")
        if last_msg is None:
            # No messages yet, check if we've been waiting too long since start
            last_restart = self._state.get("last_restart_timestamp")
            if last_restart is None:
                return False  # Just started, give it time
            return time.time() - last_restart > self.stale_threshold

        elapsed = time.time() - last_msg
        return elapsed > self.stale_threshold

    def _restart_gateway(self) -> bool:
        """Restart the OpenClaw gateway process.

        Returns:
            True if restart succeeded, False otherwise.
        """
        logger.warning("Restarting OpenClaw gateway due to stale polling")

        # Update state
        self._state["restart_count"] = self._state.get("restart_count", 0) + 1
        self._state["last_restart_timestamp"] = time.time()
        self._state["last_restart_reason"] = "stale_polling"
        self._save_state()

        # Send notification if callback provided
        if self.notify_callback:
            restart_count = self._state["restart_count"]
            self.notify_callback(
                f"🔄 *Gateway Restarted* (watchdog)\n\n"
                f"Reason: No messages received for {self.stale_threshold}s\n"
                f"Restart count: {restart_count}"
            )

        try:
            # Kill existing gateway
            pid_file = Path("/workspace/state/gateway.pid")
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    os.kill(pid, signal.SIGTERM)
                    # Wait for process to terminate
                    time.sleep(2)
                    try:
                        os.kill(pid, 0)  # Check if still exists
                        os.kill(pid, signal.SIGKILL)  # Force kill
                    except ProcessLookupError:
                        pass  # Already terminated
                except (ValueError, ProcessLookupError, PermissionError) as e:
                    logger.debug("Process already terminated or error: %s", e)

            # Start new gateway
            log_file = open("/workspace/logs/openclaw-gateway.log", "a")
            proc = subprocess.Popen(
                ["openclaw", "gateway", "run"],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

            # Save new PID
            pid_file.write_text(str(proc.pid))

            # Wait a moment and check if process is still alive
            time.sleep(5)
            try:
                os.kill(proc.pid, 0)
                logger.info("Gateway restarted successfully (PID %d)", proc.pid)
                return True
            except ProcessLookupError:
                logger.error("Gateway process died immediately after restart")
                return False

        except Exception as e:
            logger.exception("Failed to restart gateway: %s", e)
            return False

    def _check_gateway_health(self) -> bool:
        """Check if gateway process is running.

        Returns:
            True if gateway is running, False otherwise.
        """
        pid_file = Path("/workspace/state/gateway.pid")
        if not pid_file.exists():
            return False

        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ValueError, ProcessLookupError, PermissionError):
            return False

    def run_cycle(self) -> None:
        """Run one watchdog cycle."""
        self._state = self._load_state()

        # Check if gateway is running
        if not self._check_gateway_health():
            logger.warning("Gateway not running, starting it")
            self._restart_gateway()
            return

        # Check for new messages
        if self._check_for_new_messages():
            self._state["last_message_timestamp"] = time.time()
            self._save_state()
            logger.debug("Updated last message timestamp")

        # Check if stale
        if self._is_stale():
            logger.warning(
                "Gateway stale detected (no messages for %ds)",
                self.stale_threshold,
            )
            self._restart_gateway()
        else:
            last_msg = self._state.get("last_message_timestamp")
            if last_msg:
                elapsed = time.time() - last_msg
                logger.debug("Gateway healthy (last message %ds ago)", elapsed)
            else:
                logger.debug("Gateway healthy (no messages yet)")

    def run(self) -> None:
        """Run the watchdog loop continuously."""
        self._running = True
        logger.info(
            "Gateway watchdog started (stale_threshold=%ds, check_interval=%ds)",
            self.stale_threshold,
            self.check_interval,
        )

        # Setup signal handlers
        def signal_handler(signum, frame):  # noqa: ARG001
            logger.info("Received signal %d, shutting down", signum)
            self._running = False

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        while self._running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.exception("Error in watchdog cycle: %s", e)

            # Sleep with interrupt handling
            for _ in range(self.check_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Gateway watchdog stopped")


def send_telegram_notification(message: str) -> None:
    """Send notification via Telegram bot."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return

    try:
        import urllib.request
        import json

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "parse_mode": "Markdown",
            "text": message,
        }).encode()

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning("Failed to send Telegram notification: %s", e)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OpenClaw Gateway Watchdog",
    )
    parser.add_argument(
        "--state-file",
        default=DEFAULT_STATE_FILE,
        help="Path to state file",
    )
    parser.add_argument(
        "--stale-threshold",
        type=int,
        default=DEFAULT_STALE_THRESHOLD_SECONDS,
        help="Seconds without messages before considering stale",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=DEFAULT_CHECK_INTERVAL_SECONDS,
        help="Seconds between health checks",
    )
    parser.add_argument(
        "--gateway-log",
        default=DEFAULT_GATEWAY_LOG,
        help="Path to gateway log file",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send Telegram notifications on restart",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon (background process)",
    )
    parser.add_argument(
        "--log-file",
        default=DEFAULT_LOG_FILE,
        help="Path to watchdog log file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_format = "%(asctime)s | %(levelname)-8s | %(message)s"

    if args.log_file:
        log_path = Path(args.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=log_level,
            format=log_format,
            handlers=[
                logging.FileHandler(args.log_file),
                logging.StreamHandler(sys.stdout),
            ],
        )
    else:
        logging.basicConfig(level=log_level, format=log_format)

    notify_callback = send_telegram_notification if args.notify else None

    watchdog = GatewayWatchdog(
        state_file=args.state_file,
        stale_threshold=args.stale_threshold,
        check_interval=args.check_interval,
        gateway_log=args.gateway_log,
        notify_callback=notify_callback,
    )

    if args.daemon:
        # Fork to background
        pid = os.fork()
        if pid > 0:
            # Parent exit
            print(f"Watchdog started (PID {pid})")
            return 0

    try:
        watchdog.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
