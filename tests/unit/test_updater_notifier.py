"""Tests for gasclaw.updater.notifier."""

from __future__ import annotations

import httpx
import respx

from gasclaw.updater.notifier import notify_telegram


class TestNotifyTelegram:
    @respx.mock
    def test_posts_to_gateway(self):
        route = respx.post("http://localhost:18789/api/message").mock(
            return_value=httpx.Response(200)
        )
        notify_telegram("Test message", gateway_port=18789, auth_token="tok123")
        assert route.called

    @respx.mock
    def test_sends_message_body(self):
        route = respx.post("http://localhost:18789/api/message").mock(
            return_value=httpx.Response(200)
        )
        notify_telegram("Hello world", gateway_port=18789, auth_token="tok")
        request = route.calls[0].request
        assert b"Hello world" in request.content

    @respx.mock
    def test_handles_gateway_down(self):
        respx.post("http://localhost:18789/api/message").mock(
            side_effect=httpx.ConnectError("down")
        )
        # Should not raise — just log
        notify_telegram("Test", gateway_port=18789, auth_token="tok")
