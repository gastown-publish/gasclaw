"""Send notifications through OpenClaw gateway to Telegram."""

from __future__ import annotations

import json

import httpx


def notify_telegram(
    message: str,
    *,
    gateway_port: int = 18789,
    auth_token: str = "",
) -> None:
    """Send a notification message via OpenClaw gateway.

    Args:
        message: The message text to send.
        gateway_port: OpenClaw gateway port.
        auth_token: Gateway auth token.
    """
    url = f"http://localhost:{gateway_port}/api/message"
    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    try:
        httpx.post(
            url,
            content=json.dumps({"message": message}),
            headers=headers,
            timeout=10.0,
        )
    except (httpx.ConnectError, httpx.TimeoutException):
        pass  # Gateway not available — silently skip
