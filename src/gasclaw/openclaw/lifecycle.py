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
    timeout: int = 30,
) -> None:
    """Start OpenClaw gateway and wait for it to be ready.

    Args:
        port: Gateway port.
        timeout: Max seconds to wait for readiness.

    Raises:
        RuntimeError: If the openclaw process exits early.
        TimeoutError: If openclaw is not ready within the timeout.

    """
    proc = subprocess.Popen(
        ["openclaw", "gateway", "start", "--port", str(port)],
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
    except Exception:
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
