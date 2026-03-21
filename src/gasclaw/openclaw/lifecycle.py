"""OpenClaw service lifecycle: start/stop gateway."""

from __future__ import annotations

import logging
import subprocess
import time

import httpx

__all__ = ["start_openclaw", "stop_openclaw"]

logger = logging.getLogger(__name__)


def start_openclaw(
    *,
    port: int = 18789,
    timeout: int = 60,
) -> None:
    """Start OpenClaw gateway and wait for it to be ready.
    
    Uses `gateway run` (foreground) for container compatibility instead of
    `gateway start` which requires systemd.

    Args:
        port: Gateway port.
        timeout: Max seconds to wait for readiness.

    Raises:
        RuntimeError: If the openclaw process exits early.
        TimeoutError: If openclaw is not ready within the timeout.

    """
    # Use `gateway run` for container environments (no systemd required) (#316)
    proc = subprocess.Popen(
        ["openclaw", "gateway", "run", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for health endpoint to be ready
        health_url = f"http://localhost:{port}/health"
        deadline = time.time() + timeout
        while time.time() < deadline:
            # Check if process died early
            if proc.poll() is not None:
                raise RuntimeError(f"OpenClaw process exited early with code {proc.returncode}")

            try:
                response = httpx.get(health_url, timeout=2)
                if response.status_code == 200:
                    logger.info("OpenClaw gateway ready on port %d", port)
                    return
            except httpx.ConnectError:
                # Not ready yet, wait
                pass
            time.sleep(1)

        raise TimeoutError(f"OpenClaw not ready after {timeout}s on port {port}")
    except Exception:  # noqa: BLE001
        # Clean up subprocess on any failure
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        raise


def stop_openclaw(*, timeout: int = 30) -> None:
    """Stop OpenClaw gateway.

    Args:
        timeout: Max seconds to wait for shutdown.

    """
    try:
        # Try graceful shutdown first
        subprocess.run(
            ["openclaw", "gateway", "stop"],
            check=False,
            timeout=timeout,
        )
        logger.info("OpenClaw gateway stopped")
    except FileNotFoundError:
        logger.debug("openclaw not found in PATH")
    except subprocess.TimeoutExpired:
        logger.warning("Timeout stopping OpenClaw gateway")
    except Exception as e:  # noqa: BLE001
        logger.warning("Error stopping OpenClaw: %s", e)
    
    # Also kill any remaining openclaw gateway run processes
    try:
        subprocess.run(
            ["pkill", "-f", "openclaw gateway run"],
            check=False,
            timeout=5,
        )
    except Exception:  # noqa: BLE001
        pass
