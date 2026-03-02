"""Shared fixtures and mock factories for gasclaw tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def env_vars():
    """Factory for creating valid environment variable dicts."""

    def _make(**overrides):
        defaults = {
            "GASTOWN_KIMI_KEYS": "sk-kimi-key1:sk-kimi-key2",
            "OPENCLAW_KIMI_KEY": "sk-kimi-openclaw",
            "TELEGRAM_BOT_TOKEN": "123456:ABC-DEF",
            "TELEGRAM_OWNER_ID": "987654321",
        }
        defaults.update(overrides)
        return defaults

    return _make
