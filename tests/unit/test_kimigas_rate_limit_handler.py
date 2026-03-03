"""Tests for gasclaw.kimigas.rate_limit_handler."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from gasclaw.kimigas.rate_limit_handler import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_BACKOFF_MAX,
    RATE_LIMIT_STATE_FILE,
    RateLimitError,
    RateLimitHandler,
    RateLimitState,
    with_rate_limit_handling,
)


class TestRateLimitState:
    """Tests for RateLimitState dataclass."""

    def test_default_state(self):
        """Default state has all None/ zero values."""
        state = RateLimitState()
        assert state.last_rate_limit_hit is None
        assert state.backoff_level == 0
        assert state.cooldown_expiry is None
        assert state.total_hits == 0

    def test_to_dict(self):
        """State converts to dictionary correctly."""
        state = RateLimitState(
            last_rate_limit_hit=1234.5,
            backoff_level=3,
            cooldown_expiry=5678.9,
            total_hits=10,
        )
        d = state.to_dict()
        assert d["last_rate_limit_hit"] == 1234.5
        assert d["backoff_level"] == 3
        assert d["cooldown_expiry"] == 5678.9
        assert d["total_hits"] == 10

    def test_from_dict(self):
        """State can be created from dictionary."""
        data = {
            "last_rate_limit_hit": 1234.5,
            "backoff_level": 3,
            "cooldown_expiry": 5678.9,
            "total_hits": 10,
        }
        state = RateLimitState.from_dict(data)
        assert state.last_rate_limit_hit == 1234.5
        assert state.backoff_level == 3
        assert state.cooldown_expiry == 5678.9
        assert state.total_hits == 10

    def test_from_dict_with_defaults(self):
        """State from_dict uses defaults for missing keys."""
        data = {"last_rate_limit_hit": 1234.5}
        state = RateLimitState.from_dict(data)
        assert state.last_rate_limit_hit == 1234.5
        assert state.backoff_level == 0
        assert state.cooldown_expiry is None
        assert state.total_hits == 0

    def test_is_in_cooldown_when_expiry_in_future(self):
        """is_in_cooldown returns True when expiry is in future."""
        state = RateLimitState(cooldown_expiry=time.time() + 100)
        assert state.is_in_cooldown() is True

    def test_is_in_cooldown_when_expiry_in_past(self):
        """is_in_cooldown returns False when expiry is in past."""
        state = RateLimitState(cooldown_expiry=time.time() - 100)
        assert state.is_in_cooldown() is False

    def test_is_in_cooldown_when_no_expiry(self):
        """is_in_cooldown returns False when no expiry set."""
        state = RateLimitState()
        assert state.is_in_cooldown() is False

    def test_get_remaining_cooldown_with_time_remaining(self):
        """get_remaining_cooldown returns positive time when in cooldown."""
        remaining = 50.0
        state = RateLimitState(cooldown_expiry=time.time() + remaining)
        result = state.get_remaining_cooldown()
        # Allow for small timing differences
        assert 49 <= result <= 51

    def test_get_remaining_cooldown_when_expired(self):
        """get_remaining_cooldown returns 0 when cooldown expired."""
        state = RateLimitState(cooldown_expiry=time.time() - 100)
        assert state.get_remaining_cooldown() == 0.0

    def test_get_remaining_cooldown_when_no_expiry(self):
        """get_remaining_cooldown returns 0 when no expiry set."""
        state = RateLimitState()
        assert state.get_remaining_cooldown() == 0.0


class TestRateLimitError:
    """Tests for RateLimitError exception."""

    def test_basic_error(self):
        """RateLimitError can be raised with message."""
        with pytest.raises(RateLimitError, match="rate limited"):
            raise RateLimitError("rate limited")

    def test_error_with_retry_after(self):
        """RateLimitError stores retry_after value."""
        err = RateLimitError("rate limited", retry_after=60)
        assert err.retry_after == 60

    def test_error_without_retry_after(self):
        """RateLimitError has None retry_after when not provided."""
        err = RateLimitError("rate limited")
        assert err.retry_after is None


class TestRateLimitHandlerInit:
    """Tests for RateLimitHandler initialization."""

    def test_default_init(self, tmp_path):
        """Handler initializes with default values."""
        handler = RateLimitHandler()
        assert handler.backoff_base == DEFAULT_BACKOFF_BASE
        assert handler.backoff_max == DEFAULT_BACKOFF_MAX
        assert handler.backoff_factor == DEFAULT_BACKOFF_FACTOR
        assert handler.gateway_port == 18789
        assert handler.auth_token == ""
        assert handler._state is None

    def test_custom_init(self, tmp_path):
        """Handler initializes with custom values."""
        state_dir = tmp_path / "state"
        handler = RateLimitHandler(
            state_dir=state_dir,
            backoff_base=2.0,
            backoff_max=120.0,
            backoff_factor=3.0,
            gateway_port=9999,
            auth_token="secret",
        )
        assert handler.state_dir == state_dir
        assert handler.backoff_base == 2.0
        assert handler.backoff_max == 120.0
        assert handler.backoff_factor == 3.0
        assert handler.gateway_port == 9999
        assert handler.auth_token == "secret"

    def test_state_file_path(self, tmp_path):
        """State file path is constructed correctly."""
        handler = RateLimitHandler(state_dir=tmp_path)
        assert handler.state_file == tmp_path / RATE_LIMIT_STATE_FILE


class TestRateLimitHandlerStatePersistence:
    """Tests for state loading and saving."""

    def test_load_state_creates_default_if_no_file(self, tmp_path):
        """Loading state creates default when file doesn't exist."""
        handler = RateLimitHandler(state_dir=tmp_path)
        state = handler._load_state()
        assert isinstance(state, RateLimitState)
        assert state.backoff_level == 0

    def test_save_and_load_state(self, tmp_path):
        """State can be saved and loaded."""
        handler = RateLimitHandler(state_dir=tmp_path)
        state = RateLimitState(
            last_rate_limit_hit=1234.5,
            backoff_level=5,
            cooldown_expiry=5678.9,
            total_hits=42,
        )
        handler._save_state(state)

        # Load in new handler instance
        handler2 = RateLimitHandler(state_dir=tmp_path)
        loaded = handler2._load_state()
        assert loaded.last_rate_limit_hit == 1234.5
        assert loaded.backoff_level == 5
        assert loaded.cooldown_expiry == 5678.9
        assert loaded.total_hits == 42

    def test_load_corrupted_state_returns_default(self, tmp_path, caplog):
        """Loading corrupted state returns default and logs warning."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.state_dir.mkdir(parents=True, exist_ok=True)
        handler.state_file.write_text("not valid json!")

        state = handler._load_state()
        assert isinstance(state, RateLimitState)
        assert state.backoff_level == 0
        assert "Failed to load rate limit state" in caplog.text

    def test_get_state_caches(self, tmp_path):
        """get_state caches the loaded state."""
        handler = RateLimitHandler(state_dir=tmp_path)
        state1 = handler.get_state()
        state2 = handler.get_state()
        assert state1 is state2

    def test_save_state_creates_directories(self, tmp_path):
        """save_state creates parent directories if needed."""
        nested = tmp_path / "nested" / "deep"
        handler = RateLimitHandler(state_dir=nested)
        state = RateLimitState()
        handler._save_state(state)
        assert nested.exists()

    def test_save_state_clears_temp_on_failure(self, tmp_path, monkeypatch):
        """Temp file is cleaned up if state save fails."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.state_dir.mkdir(parents=True, exist_ok=True)

        def fail_dump(*args, **kwargs):
            raise TypeError("Cannot serialize")

        monkeypatch.setattr(json, "dump", fail_dump)

        with pytest.raises(TypeError):
            handler._save_state(RateLimitState())

        # No temp files should remain
        temps = list(tmp_path.glob(".rate-limit-*.tmp"))
        assert len(temps) == 0


class TestRateLimitHandlerBackoff:
    """Tests for backoff calculation."""

    def test_calculate_backoff_level_0(self):
        """Backoff at level 0 is the base value."""
        handler = RateLimitHandler()
        assert handler.calculate_backoff(0) == DEFAULT_BACKOFF_BASE

    def test_calculate_backoff_exponential(self):
        """Backoff increases exponentially."""
        handler = RateLimitHandler()
        level0 = handler.calculate_backoff(0)
        level1 = handler.calculate_backoff(1)
        level2 = handler.calculate_backoff(2)

        assert level1 == level0 * DEFAULT_BACKOFF_FACTOR
        assert level2 == level1 * DEFAULT_BACKOFF_FACTOR

    def test_calculate_backoff_respects_max(self):
        """Backoff is capped at max value."""
        handler = RateLimitHandler()
        # High level would exceed max
        backoff = handler.calculate_backoff(100)
        assert backoff == DEFAULT_BACKOFF_MAX

    def test_custom_backoff_parameters(self):
        """Custom backoff parameters are respected."""
        handler = RateLimitHandler(backoff_base=5.0, backoff_factor=2.0, backoff_max=50.0)
        assert handler.calculate_backoff(0) == 5.0
        assert handler.calculate_backoff(1) == 10.0
        assert handler.calculate_backoff(2) == 20.0
        assert handler.calculate_backoff(10) == 50.0  # capped


class TestRateLimitHandlerReport:
    """Tests for report_rate_limit method."""

    def test_report_updates_state(self, tmp_path):
        """Reporting rate limit updates state correctly."""
        handler = RateLimitHandler(state_dir=tmp_path)
        before = time.time()
        state = handler.report_rate_limit()
        after = time.time()

        assert state.total_hits == 1
        assert state.backoff_level == 1
        assert before <= state.last_rate_limit_hit <= after
        assert state.cooldown_expiry is not None

    def test_report_increments_backoff_level(self, tmp_path):
        """Each report increments backoff level."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.report_rate_limit()
        handler.report_rate_limit()
        state = handler.report_rate_limit()

        assert state.total_hits == 3
        assert state.backoff_level == 3

    def test_report_with_retry_after_uses_provided_value(self, tmp_path):
        """When retry_after is provided, it's used instead of calculated backoff."""
        handler = RateLimitHandler(state_dir=tmp_path)
        before = time.time()
        state = handler.report_rate_limit(retry_after=30)

        expected_expiry = before + 30
        assert state.cooldown_expiry is not None
        assert expected_expiry - 1 <= state.cooldown_expiry <= expected_expiry + 1

    def test_report_with_zero_retry_after_uses_calculated(self, tmp_path):
        """Zero retry_after uses calculated backoff."""
        handler = RateLimitHandler(state_dir=tmp_path)
        state = handler.report_rate_limit(retry_after=0)

        # Should use exponential backoff, not 0
        assert state.cooldown_expiry is not None
        assert state.cooldown_expiry > time.time()


class TestRateLimitHandlerClear:
    """Tests for clear_rate_limit method."""

    def test_clear_resets_backoff_level(self, tmp_path):
        """Clearing resets backoff level to 0."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.report_rate_limit()
        handler.clear_rate_limit()

        state = handler.get_state()
        assert state.backoff_level == 0
        assert state.cooldown_expiry is None

    def test_clear_when_already_clear(self, tmp_path, caplog):
        """Clearing when already clear does nothing gracefully."""
        handler = RateLimitHandler(state_dir=tmp_path)
        # No rate limit set yet
        handler.clear_rate_limit()
        # Should not raise or cause issues
        assert handler.get_state().backoff_level == 0

    def test_clear_resets_notification_flag(self, tmp_path):
        """Clearing resets the notification sent flag."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler._notification_sent = True
        handler.report_rate_limit()
        handler.clear_rate_limit()

        assert handler._notification_sent is False


class TestRateLimitHandlerWait:
    """Tests for wait_if_rate_limited method."""

    def test_wait_when_not_limited_returns_zero(self, tmp_path):
        """wait_if_rate_limited returns 0 when not rate limited."""
        handler = RateLimitHandler(state_dir=tmp_path)
        waited = handler.wait_if_rate_limited()
        assert waited == 0.0

    def test_wait_when_limited_sleeps(self, tmp_path, monkeypatch):
        """wait_if_rate_limited sleeps when rate limited."""
        handler = RateLimitHandler(state_dir=tmp_path)

        # Set up rate limit with short cooldown
        handler.report_rate_limit(retry_after=0.01)

        sleep_calls = []
        def mock_sleep(seconds):
            sleep_calls.append(seconds)

        monkeypatch.setattr(time, "sleep", mock_sleep)

        waited = handler.wait_if_rate_limited()

        assert len(sleep_calls) == 1
        assert waited > 0

    def test_wait_when_cooldown_expired(self, tmp_path):
        """wait_if_rate_limited returns 0 when cooldown expired."""
        handler = RateLimitHandler(state_dir=tmp_path)

        # Set rate limit that immediately expires
        handler.report_rate_limit(retry_after=0.001)
        time.sleep(0.01)  # Wait for cooldown to expire

        waited = handler.wait_if_rate_limited()
        assert waited == 0.0


class TestRateLimitHandlerRetry:
    """Tests for should_retry method."""

    def test_should_retry_within_max_attempts(self):
        """should_retry returns True within max attempts."""
        handler = RateLimitHandler()
        assert handler.should_retry(0, max_attempts=5) is True
        assert handler.should_retry(4, max_attempts=5) is True

    def test_should_retry_at_max_attempts(self):
        """should_retry returns False at max attempts."""
        handler = RateLimitHandler()
        assert handler.should_retry(5, max_attempts=5) is False

    def test_should_retry_past_max_attempts(self):
        """should_retry returns False past max attempts."""
        handler = RateLimitHandler()
        assert handler.should_retry(10, max_attempts=5) is False


class TestRateLimitHandlerNotification:
    """Tests for send_notification method."""

    def test_send_notification_first_time(self, tmp_path):
        """First notification is sent successfully."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.report_rate_limit()

        with patch("gasclaw.kimigas.rate_limit_handler.notify_telegram") as mock_notify:
            mock_notify.return_value = True
            result = handler.send_notification()

        assert result is True
        assert handler._notification_sent is True
        mock_notify.assert_called_once()

    def test_send_notification_skips_if_already_sent(self, tmp_path):
        """Notification is skipped if already sent."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler._notification_sent = True

        with patch("gasclaw.kimigas.rate_limit_handler.notify_telegram") as mock_notify:
            result = handler.send_notification()

        assert result is True
        assert mock_notify.call_count == 0

    def test_send_notification_uses_default_message(self, tmp_path):
        """Default message includes rate limit details."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.report_rate_limit()

        with patch("gasclaw.kimigas.rate_limit_handler.notify_telegram") as mock_notify:
            mock_notify.return_value = True
            handler.send_notification()

        call_args = mock_notify.call_args
        message = call_args[0][0]
        assert "Rate Limit Alert" in message
        assert "backoff level" in message.lower()

    def test_send_notification_uses_custom_message(self, tmp_path):
        """Custom message can be provided."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.report_rate_limit()

        custom_msg = "Custom alert message"

        with patch("gasclaw.kimigas.rate_limit_handler.notify_telegram") as mock_notify:
            mock_notify.return_value = True
            handler.send_notification(message=custom_msg)

        mock_notify.assert_called_once_with(
            custom_msg,
            gateway_port=handler.gateway_port,
            auth_token=handler.auth_token,
        )

    def test_send_notification_handles_failure(self, tmp_path):
        """Failed notification returns False and doesn't set flag."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.report_rate_limit()

        with patch("gasclaw.kimigas.rate_limit_handler.notify_telegram") as mock_notify:
            mock_notify.return_value = False
            result = handler.send_notification()

        assert result is False
        assert handler._notification_sent is False

    def test_send_notification_handles_exception(self, tmp_path, caplog):
        """Exception during notification is logged and returns False."""
        handler = RateLimitHandler(state_dir=tmp_path)
        handler.report_rate_limit()

        with patch("gasclaw.kimigas.rate_limit_handler.notify_telegram") as mock_notify:
            mock_notify.side_effect = Exception("Network error")
            result = handler.send_notification()

        assert result is False
        assert "Failed to send rate limit notification" in caplog.text


class TestRateLimitHandlerStatus:
    """Tests for get_status method."""

    def test_status_when_not_rate_limited(self, tmp_path):
        """Status shows not rate limited when clear."""
        handler = RateLimitHandler(state_dir=tmp_path)
        status = handler.get_status()

        assert status["rate_limited"] is False
        assert status["backoff_level"] == 0
        assert status["total_hits"] == 0
        assert status["cooldown_remaining"] == 0.0
        assert status["last_hit"] is None

    def test_status_when_rate_limited(self, tmp_path):
        """Status shows rate limited state correctly."""
        handler = RateLimitHandler(state_dir=tmp_path)
        # Use calculated backoff to also increment backoff_level
        handler.report_rate_limit()

        status = handler.get_status()

        assert status["rate_limited"] is True
        assert status["backoff_level"] == 1
        assert status["total_hits"] == 1
        assert status["cooldown_remaining"] > 0
        assert status["last_hit"] is not None


class TestWithRateLimitHandling:
    """Tests for with_rate_limit_handling decorator."""

    def test_decorator_allows_successful_function(self, tmp_path):
        """Decorator allows successful function execution."""
        handler = RateLimitHandler(state_dir=tmp_path)

        @with_rate_limit_handling(handler)
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

    def test_decorator_clears_rate_limit_on_success(self, tmp_path):
        """Decorator clears rate limit state on success."""
        handler = RateLimitHandler(state_dir=tmp_path)

        @with_rate_limit_handling(handler)
        def success_func():
            return "success"

        # Set up rate limit state
        handler.report_rate_limit()
        assert handler.get_state().backoff_level == 1

        success_func()

        # State should be cleared
        assert handler.get_state().backoff_level == 0

    def test_decorator_retries_on_rate_limit_error(self, tmp_path, monkeypatch):
        """Decorator retries when RateLimitError is raised."""
        handler = RateLimitHandler(state_dir=tmp_path)

        call_count = 0

        @with_rate_limit_handling(handler, max_attempts=3)
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("rate limited", retry_after=0.001)
            return "success"

        # Mock sleep to speed up test
        monkeypatch.setattr(time, "sleep", lambda x: None)

        result = flaky_func()

        assert result == "success"
        assert call_count == 3

    def test_decorator_sends_notification_on_first_failure(self, tmp_path, monkeypatch):
        """Decorator sends notification on first rate limit."""
        handler = RateLimitHandler(state_dir=tmp_path)

        notification_sent = []

        def mock_notify(*args, **kwargs):
            notification_sent.append(True)
            return True

        monkeypatch.setattr(handler, "send_notification", mock_notify)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        @with_rate_limit_handling(handler, max_attempts=2)
        def failing_func():
            raise RateLimitError("rate limited")

        with pytest.raises(RateLimitError):
            failing_func()

        assert len(notification_sent) == 1

    def test_decorator_raises_after_max_attempts(self, tmp_path, monkeypatch):
        """Decorator raises RateLimitError after max attempts."""
        handler = RateLimitHandler(state_dir=tmp_path)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        @with_rate_limit_handling(handler, max_attempts=2)
        def always_fails():
            raise RateLimitError("rate limited")

        with pytest.raises(RateLimitError, match="Max attempts"):
            always_fails()

    def test_decorator_passes_through_other_exceptions(self, tmp_path):
        """Decorator doesn't catch non-RateLimitError exceptions."""
        handler = RateLimitHandler(state_dir=tmp_path)

        @with_rate_limit_handling(handler)
        def raises_other():
            raise ValueError("other error")

        with pytest.raises(ValueError, match="other error"):
            raises_other()

    def test_decorator_with_notify_false(self, tmp_path, monkeypatch):
        """Decorator doesn't notify when notify=False."""
        handler = RateLimitHandler(state_dir=tmp_path)

        notification_sent = []

        def mock_notify(*args, **kwargs):
            notification_sent.append(True)
            return True

        monkeypatch.setattr(handler, "send_notification", mock_notify)
        monkeypatch.setattr(time, "sleep", lambda x: None)

        @with_rate_limit_handling(handler, max_attempts=1, notify=False)
        def failing_func():
            raise RateLimitError("rate limited")

        with pytest.raises(RateLimitError):
            failing_func()

        assert len(notification_sent) == 0
