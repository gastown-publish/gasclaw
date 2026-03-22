"""Gastown service lifecycle: start/stop Dolt, daemon, mayor."""

from __future__ import annotations

import logging
import socket
import subprocess
import time
from pathlib import Path

__all__ = ["start_dolt", "start_daemon", "start_mayor", "stop_all"]

logger = logging.getLogger(__name__)


def start_dolt(
    *,
    data_dir: str = "/workspace/gt/.dolt-data",
    port: int = 3307,
    timeout: int = 30,
) -> None:
    """Start Dolt SQL server and wait for it to be ready.

    Args:
        data_dir: Directory for Dolt data files.
        port: SQL server port.
        timeout: Max seconds to wait for readiness.

    Raises:
        RuntimeError: If the dolt process exits early.
        TimeoutError: If dolt is not ready within the timeout.

    """
    # Ensure data dir exists and is initialized (first boot)
    data_path = Path(data_dir)
    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["dolt", "init"], cwd=str(data_path), check=True)
        logger.info("Initialized fresh Dolt database at %s", data_dir)

    proc = subprocess.Popen(
        ["dolt", "sql-server", "--port", str(port), "--data-dir", data_dir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for port to be ready
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Check if process died early
            if proc.poll() is not None:
                raise RuntimeError(f"Dolt process exited early with code {proc.returncode}")

            # TCP check — dolt sql --port is not a valid flag
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            try:
                sock.connect(("127.0.0.1", port))
                sock.close()
                logger.info("Dolt SQL server ready on port %d", port)
                return
            except (ConnectionRefusedError, OSError):
                sock.close()
            time.sleep(1)
        raise TimeoutError(f"Dolt not ready after {timeout}s on port {port}")
    except Exception:  # noqa: BLE001
        # Clean up subprocess on any failure
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        raise


def start_daemon(*, gt_root: str = "/workspace/gt") -> None:
    """Start the Gastown daemon."""
    subprocess.run(["gt", "daemon", "start"], check=True, cwd=gt_root)


def start_mayor(*, agent: str = "kimi-claude", gt_root: str = "/workspace/gt") -> None:
    """Start the Gastown mayor.

    Args:
        agent: Agent name to use (default: kimi-claude).
        gt_root: Gastown workspace directory.

    """
    subprocess.run(
        ["gt", "mayor", "start", "--agent", agent],
        check=True,
        cwd=gt_root,
    )


def stop_all(*, gt_root: str = "/workspace/gt") -> None:
    """Stop all Gastown services (mayor, daemon, dolt).

    All stop commands are attempted even if one fails. Exceptions are logged
    but not raised to ensure best-effort shutdown.
    """
    commands = [
        ["gt", "mayor", "stop"],
        ["gt", "daemon", "stop"],
        ["pkill", "-f", "dolt sql-server"],
    ]

    for cmd in commands:
        try:
            subprocess.run(cmd, check=False, timeout=30, cwd=gt_root)
        except FileNotFoundError:
            logger.debug("Command not found: %s", cmd[0])
        except subprocess.TimeoutExpired:
            logger.warning("Timeout stopping service: %s", cmd)
        except Exception as e:  # noqa: BLE001
            logger.warning("Error stopping service %s: %s", cmd, e)
