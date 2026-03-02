"""Send notifications through OpenClaw gateway to Telegram."""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

__all__ = ["notify_telegram"]


def notify_telegram(
    message: str,
    *,
    gateway_port: int = 18789,
    auth_token: str = "",
) -> bool:
    """Send a notification message via OpenClaw gateway.

    Args:
        message: The message text to send.
        gateway_port: OpenClaw gateway port.
        auth_token: Gateway auth token.

    Returns:
        True if notification was sent successfully, False otherwise.
    """
    url = f"http://localhost:{gateway_port}/api/message"
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        response = httpx.post(
            url,
            content=json.dumps({"message": message}),
            headers=headers,
            timeout=10.0,
        )
        return response.is_success
    except httpx.ConnectError as e:
        logger.warning("Failed to send notification: gateway not available (%s)", e)
        return False
    except httpx.TimeoutException as e:
        logger.warning("Failed to send notification: gateway timeout (%s)", e)
        return False
