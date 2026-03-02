"""LRU key rotation pool for Kimi API keys.

Ported from kimigas key_rotation.py — simplified since keys come from config
rather than account discovery.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, cast

RATE_LIMIT_COOLDOWN = 300  # 5 minutes

__all__ = ["KeyPool", "RATE_LIMIT_COOLDOWN"]


class KeyPool:
    """LRU-based API key rotation pool."""

    def __init__(self, keys: list[str], *, state_dir: Path | None = None) -> None:
        if not keys:
            raise ValueError("KeyPool requires at least one key")
        self._keys = list(keys)
        self._state_dir = state_dir or Path.home() / ".gasclaw"

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    @staticmethod
    def _key_hash(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    def _load_state(self) -> dict[str, Any]:
        state_file = self._state_dir / "key-rotation.json"
        if state_file.is_file():
            try:
                return cast(dict[str, Any], json.loads(state_file.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        """Save the key rotation state to disk atomically.

        Uses atomic write (write to temp file, then rename) to avoid
        race conditions where the file could be corrupted during read.
        """
        self._state_dir.mkdir(parents=True, exist_ok=True)
        state_file = self._state_dir / "key-rotation.json"

        # Write to temp file in same directory, then rename atomically
        fd, temp_path = tempfile.mkstemp(
            dir=self._state_dir, prefix=".key-rotation-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2)
            os.replace(temp_path, state_file)
        except Exception:
            # Clean up temp file on failure
            with contextlib.suppress(OSError):
                os.unlink(temp_path)
            raise

    def get_key(self) -> str:
        """Select the best available key using LRU rotation."""
        if len(self._keys) == 1:
            self._record_usage(self._keys[0])
            return self._keys[0]

        state = self._load_state()
        now = time.time()

        rate_limited: dict[str, float] = state.get("rate_limited", {})
        available = [
            k
            for k in self._keys
            if now - rate_limited.get(self._key_hash(k), 0) > RATE_LIMIT_COOLDOWN
        ]

        # If all rate-limited, use all (pick LRU)
        if not available:
            available = list(self._keys)

        # LRU: pick least recently used
        last_used: dict[str, float] = state.get("last_used", {})
        available.sort(key=lambda k: last_used.get(self._key_hash(k), 0))
        selected = available[0]

        self._record_usage(selected)
        return selected

    def _record_usage(self, key: str) -> None:
        state = self._load_state()
        last_used = state.get("last_used", {})
        last_used[self._key_hash(key)] = time.time()
        state["last_used"] = last_used
        self._save_state(state)

    def mark_rate_limited(self, key: str) -> None:
        """Mark a key as rate-limited (enters cooldown)."""
        state = self._load_state()
        rate_limited = state.get("rate_limited", {})
        rate_limited[self._key_hash(key)] = time.time()
        state["rate_limited"] = rate_limited
        self._save_state(state)

    def status(self) -> dict[str, Any]:
        """Return pool status report."""
        state = self._load_state()
        now = time.time()
        rate_limited: dict[str, float] = state.get("rate_limited", {})

        rl_count = sum(
            1
            for k in self._keys
            if now - rate_limited.get(self._key_hash(k), 0) <= RATE_LIMIT_COOLDOWN
        )

        return {
            "total": len(self._keys),
            "available": len(self._keys) - rl_count,
            "rate_limited": rl_count,
        }
