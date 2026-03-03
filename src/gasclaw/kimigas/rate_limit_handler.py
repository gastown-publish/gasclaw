"""Rate limit handling with exponential backoff and state persistence.

This module provides centralized rate limit handling for Kimi K2.5 API calls,
with support for:
- Detecting HTTP 429 rate limit errors
- Exponential backoff with ceiling
- Persisting rate limit state to disk
- Sending notifications to Telegram discussion topic
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gasclaw.updater.notifier import notify_telegram

logger = logging.getLogger(__name__)

__all__ = [
    "RateLimitState",
    "RateLimitHandler",
    "RateLimitError",
    "with_rate_limit_handling",
]

# Default configuration
DEFAULT_BACKOFF_BASE = 1.0  # Initial backoff in seconds
DEFAULT_BACKOFF_MAX = 60.0  # Maximum backoff ceiling
DEFAULT_BACKOFF_FACTOR = 2.0  # Exponential multiplier
DEFAULT_STATE_DIR = "/workspace/state"
RATE_LIMIT_STATE_FILE = "rate_limit_state.json"


class RateLimitError(Exception):
    """Raised when a rate limit is hit."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        """Initialize rate limit error.

        Args:
            message: Error message.
            retry_after: Seconds to wait before retrying.
        """
        super().__init__(message)
        self.retry_after = retry_after


@dataclass
class RateLimitState:
    """Persisted rate limit state."""

    last_rate_limit_hit: float | None = None
    backoff_level: int = 0
    cooldown_expiry: float | None = None
    total_hits: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        return {
            "last_rate_limit_hit": self.last_rate_limit_hit,
            "backoff_level": self.backoff_level,
            "cooldown_expiry": self.cooldown_expiry,
            "total_hits": self.total_hits,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RateLimitState:
        """Create state from dictionary."""
        return cls(
            last_rate_limit_hit=data.get("last_rate_limit_hit"),
            backoff_level=data.get("backoff_level", 0),
            cooldown_expiry=data.get("cooldown_expiry"),
            total_hits=data.get("total_hits", 0),
        )

    def is_in_cooldown(self) -> bool:
        """Check if currently in rate limit cooldown."""
        if self.cooldown_expiry is None:
            return False
        return time.time() < self.cooldown_expiry

    def get_remaining_cooldown(self) -> float:
        """Get remaining cooldown time in seconds."""
        if self.cooldown_expiry is None:
            return 0.0
        remaining = self.cooldown_expiry - time.time()
        return max(0.0, remaining)


class RateLimitHandler:
    """Handle rate limiting with exponential backoff and notifications."""

    def __init__(
        self,
        state_dir: str | Path = DEFAULT_STATE_DIR,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        backoff_max: float = DEFAULT_BACKOFF_MAX,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        gateway_port: int = 18789,
        auth_token: str = "",
    ) -> None:
        """Initialize the rate limit handler.

        Args:
            state_dir: Directory to store rate limit state.
            backoff_base: Initial backoff duration in seconds.
            backoff_max: Maximum backoff ceiling in seconds.
            backoff_factor: Exponential backoff multiplier.
            gateway_port: OpenClaw gateway port for notifications.
            auth_token: Gateway auth token for notifications.
        """
        self.state_dir = Path(state_dir)
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        self.backoff_factor = backoff_factor
        self.gateway_port = gateway_port
        self.auth_token = auth_token
        self._state: RateLimitState | None = None
        self._notification_sent = False

    @property
    def state_file(self) -> Path:
        """Path to the rate limit state file."""
        return self.state_dir / RATE_LIMIT_STATE_FILE

    def _load_state(self) -> RateLimitState:
        """Load rate limit state from disk."""
        if self.state_file.is_file():
            try:
                data = json.loads(self.state_file.read_text())
                return RateLimitState.from_dict(data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load rate limit state: %s", e)
        return RateLimitState()

    def _save_state(self, state: RateLimitState) -> None:
        """Save rate limit state to disk atomically."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory, then rename atomically
        fd, temp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".rate-limit-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
            os.replace(temp_path, self.state_file)
            self._state = state
        except (OSError, TypeError, ValueError) as e:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            logger.error("Failed to save rate limit state: %s", e)
            raise

    def get_state(self) -> RateLimitState:
        """Get current rate limit state (cached or loaded)."""
        if self._state is None:
            self._state = self._load_state()
        return self._state

    def calculate_backoff(self, level: int) -> float:
        """Calculate backoff duration for a given level.

        Uses exponential backoff: base * factor^level, capped at max.

        Args:
            level: Current backoff level (0-indexed).

        Returns:
            Backoff duration in seconds.
        """
        backoff = self.backoff_base * (self.backoff_factor**level)
        return min(backoff, self.backoff_max)

    def report_rate_limit(self, retry_after: float | None = None) -> RateLimitState:
        """Report a rate limit hit and update state.

        Args:
            retry_after: Optional retry-after duration from API.

        Returns:
            Updated rate limit state.
        """
        state = self.get_state()
        now = time.time()

        state.last_rate_limit_hit = now
        state.total_hits += 1

        # If API provides retry-after, use it; otherwise use exponential backoff
        if retry_after is not None and retry_after > 0:
            backoff = retry_after
        else:
            backoff = self.calculate_backoff(state.backoff_level)
            state.backoff_level += 1

        state.cooldown_expiry = now + backoff
        self._save_state(state)

        logger.warning(
            "Rate limit hit (level=%d, backoff=%.1fs, total_hits=%d)",
            state.backoff_level,
            backoff,
            state.total_hits,
        )

        return state

    def clear_rate_limit(self) -> None:
        """Clear rate limit state (call when operation succeeds)."""
        state = self.get_state()
        if state.backoff_level > 0 or state.cooldown_expiry is not None:
            state.backoff_level = 0
            state.cooldown_expiry = None
            self._save_state(state)
            self._notification_sent = False
            logger.info("Rate limit cleared - normal operation resumed")

    def wait_if_rate_limited(self) -> float:
        """Wait if currently rate limited.

        Returns:
            Seconds waited (0 if not rate limited).
        """
        state = self.get_state()
        if not state.is_in_cooldown():
            return 0.0

        wait_time = state.get_remaining_cooldown()
        if wait_time > 0:
            logger.info("Rate limited - waiting %.1f seconds", wait_time)
            time.sleep(wait_time)
        return wait_time

    def should_retry(self, attempt: int, max_attempts: int = 5) -> bool:
        """Check if we should retry a rate-limited request.

        Args:
            attempt: Current attempt number (0-indexed).
            max_attempts: Maximum number of retry attempts.

        Returns:
            True if should retry, False otherwise.
        """
        return attempt < max_attempts

    def send_notification(self, message: str | None = None) -> bool:
        """Send rate limit notification to Telegram.

        Args:
            message: Custom notification message. If None, uses default.

        Returns:
            True if notification sent successfully, False otherwise.
        """
        if self._notification_sent:
            return True  # Don't spam notifications

        state = self.get_state()
        if not message:
            remaining = state.get_remaining_cooldown()
            message = (
                f"⚠️ *Rate Limit Alert*\n\n"
                f"The Kimi K2.5 API is currently rate-limited.\n"
                f"Backoff level: {state.backoff_level}\n"
                f"Cooldown: {remaining:.0f}s remaining\n"
                f"Total hits: {state.total_hits}\n\n"
                f"Requests will automatically retry with exponential backoff."
            )

        try:
            result = notify_telegram(
                message,
                gateway_port=self.gateway_port,
                auth_token=self.auth_token,
            )
            if result:
                self._notification_sent = True
                logger.info("Rate limit notification sent")
            return result
        except Exception as e:
            logger.warning("Failed to send rate limit notification: %s", e)
            return False

    def get_status(self) -> dict[str, Any]:
        """Get current rate limit status for health reporting.

        Returns:
            Dict with rate limit status information.
        """
        state = self.get_state()
        return {
            "rate_limited": state.is_in_cooldown(),
            "backoff_level": state.backoff_level,
            "total_hits": state.total_hits,
            "cooldown_remaining": state.get_remaining_cooldown(),
            "last_hit": state.last_rate_limit_hit,
        }


def with_rate_limit_handling(
    handler: RateLimitHandler,
    max_attempts: int = 5,
    notify: bool = True,
):
    """Decorator/context manager helper for rate limit handling.

    Usage:
        handler = RateLimitHandler()

        @with_rate_limit_handling(handler)
        def my_api_call():
            # ... make API call
            pass

    Args:
        handler: RateLimitHandler instance.
        max_attempts: Maximum retry attempts.
        notify: Whether to send Telegram notifications.

    Returns:
        Decorator function.
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                # Wait if rate limited
                handler.wait_if_rate_limited()

                try:
                    result = func(*args, **kwargs)
                    # Success - clear rate limit state
                    handler.clear_rate_limit()
                    return result
                except RateLimitError as e:
                    handler.report_rate_limit(e.retry_after)
                    if notify and attempt == 0:
                        handler.send_notification()

                    if not handler.should_retry(attempt, max_attempts):
                        raise

            # Should not reach here
            raise RateLimitError(f"Max attempts ({max_attempts}) exceeded")

        return wrapper

    return decorator
