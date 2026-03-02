"""Tests for kimigas/credit_checker.py."""

from unittest.mock import Mock, patch

import httpx
import pytest
import respx
from httpx import Response

from gasclaw.kimigas.credit_checker import (
    KIMI_API_BASE,
    CreditChecker,
    CreditInfo,
    _parse_amount,
    check_key_credits,
)


class TestCreditInfo:
    """Tests for CreditInfo dataclass."""

    def test_default_values(self):
        """CreditInfo has correct defaults."""
        info = CreditInfo(key="test-key-1234")
        assert info.key == "test-key-1234"
        assert info.balance is None
        assert info.total_used is None
        assert info.currency == "CNY"
        assert info.valid is True
        assert info.error is None

    def test_key_hash_property(self):
        """key_hash returns masked key."""
        info = CreditInfo(key="sk-verylongkey12345678")
        assert info.key_hash == "...12345678"

    def test_key_hash_short_key(self):
        """key_hash handles short keys."""
        info = CreditInfo(key="short")
        assert info.key_hash == "short"


class TestParseAmount:
    """Tests for _parse_amount helper."""

    def test_parses_float(self):
        """Parses float values."""
        assert _parse_amount(100.50) == 100.50

    def test_parses_int(self):
        """Parses int values."""
        assert _parse_amount(100) == 100.0

    def test_parses_string_number(self):
        """Parses numeric strings."""
        assert _parse_amount("99.99") == 99.99

    def test_returns_none_for_none(self):
        """Returns None for None input."""
        assert _parse_amount(None) is None

    def test_returns_none_for_invalid_string(self):
        """Returns None for non-numeric strings."""
        assert _parse_amount("not-a-number") is None

    def test_returns_none_for_inf(self):
        """Returns None for infinity."""
        assert _parse_amount(float("inf")) is None

    def test_returns_none_for_negative_inf(self):
        """Returns None for negative infinity."""
        assert _parse_amount(float("-inf")) is None

    def test_returns_none_for_nan(self):
        """Returns None for NaN."""
        assert _parse_amount(float("nan")) is None

    def test_rounds_to_two_decimals(self):
        """Rounds to 2 decimal places."""
        assert _parse_amount(100.999) == 101.0


class TestCreditCheckerInit:
    """Tests for CreditChecker initialization."""

    def test_default_base_url(self):
        """Uses default base URL."""
        checker = CreditChecker()
        assert checker.base_url == KIMI_API_BASE

    def test_custom_base_url(self):
        """Accepts custom base URL."""
        checker = CreditChecker(base_url="https://custom.api.com")
        assert checker.base_url == "https://custom.api.com"


class TestMaskKey:
    """Tests for _mask_key method."""

    def test_masks_long_key(self):
        """Shows last 8 chars for long keys."""
        checker = CreditChecker()
        assert checker._mask_key("sk-test1234567890") == "...34567890"

    def test_returns_short_key_unchanged(self):
        """Returns short keys unchanged."""
        checker = CreditChecker()
        assert checker._mask_key("short") == "short"


class TestCheckKeySuccess:
    """Tests for successful check_key calls."""

    @respx.mock
    def test_returns_credit_info_on_success(self):
        """Returns CreditInfo with balance data."""
        route = respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "available_balance": 50.00,
                        "total_usage": 150.00,
                        "currency": "CNY",
                    }
                },
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key-1234")

        assert route.called
        assert result.key == "...key-1234"
        assert result.balance == 50.00
        assert result.total_used == 150.00
        assert result.currency == "CNY"
        assert result.valid is True
        assert result.error is None

    @respx.mock
    def test_uses_default_currency(self):
        """Uses CNY when currency not in response."""
        respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "available_balance": 50.00,
                        "total_usage": 150.00,
                    }
                },
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test")

        assert result.currency == "CNY"

    @respx.mock
    def test_handles_none_balance(self):
        """Handles None balance in response."""
        respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "available_balance": None,
                        "total_usage": None,
                    }
                },
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test")

        assert result.balance is None
        assert result.total_used is None
        assert result.valid is True


class TestCheckKeyErrors:
    """Tests for check_key error handling."""

    @respx.mock
    def test_handles_401_invalid_key(self):
        """Returns invalid CreditInfo on 401."""
        route = respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(401, json={"error": "Unauthorized"})
        )

        checker = CreditChecker()
        result = checker.check_key("sk-invalid-key")

        assert route.called
        assert result.valid is False
        assert result.error == "Invalid API key"
        assert result.balance is None

    @respx.mock
    def test_handles_429_rate_limited(self):
        """Returns rate limited CreditInfo on 429."""
        route = respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(429, json={"error": "Too Many Requests"})
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert route.called
        assert result.valid is True  # Key is still valid, just rate limited
        assert result.error == "Rate limited - try again later"

    @respx.mock
    def test_handles_http_status_error(self):
        """Returns error CreditInfo on HTTP error."""
        route = respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(500, text="Internal Server Error")
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert route.called
        assert result.valid is False
        assert "HTTP 500" in result.error

    @respx.mock
    def test_handles_403_forbidden(self):
        """Returns error CreditInfo on 403."""
        respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(403, json={"error": "Forbidden"})
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert "HTTP 403" in result.error


class TestCheckKeyRequestErrors:
    """Tests for request-level error handling."""

    @patch("gasclaw.kimigas.credit_checker.httpx.Client")
    def test_handles_request_error(self, mock_client_class):
        """Returns error CreditInfo on request error."""
        mock_client = Mock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_client.get.side_effect = httpx.RequestError("Connection failed")

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert "Request failed" in result.error
        assert "Connection failed" in result.error

    @patch("gasclaw.kimigas.credit_checker.httpx.Client")
    def test_handles_connect_timeout(self, mock_client_class):
        """Returns error CreditInfo on connect timeout."""
        mock_client = Mock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectTimeout("Connection timed out")

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert "Request failed" in result.error

    @patch("gasclaw.kimigas.credit_checker.httpx.Client")
    def test_handles_read_timeout(self, mock_client_class):
        """Returns error CreditInfo on read timeout."""
        mock_client = Mock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_client.get.side_effect = httpx.ReadTimeout("Read timed out")

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert "Request failed" in result.error


class TestCheckKeyUnexpectedErrors:
    """Tests for unexpected error handling."""

    @patch("gasclaw.kimigas.credit_checker.httpx.Client")
    def test_handles_unexpected_exception(self, mock_client_class):
        """Returns error CreditInfo on unexpected exception."""
        mock_client = Mock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_client.get.side_effect = ValueError("Something unexpected")

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert result.error == "Something unexpected"

    @patch("gasclaw.kimigas.credit_checker.httpx.Client")
    def test_handles_keyboard_interrupt_not_caught(self, mock_client_class):
        """KeyboardInterrupt is not caught by generic Exception."""
        mock_client = Mock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)
        mock_client.get.side_effect = KeyboardInterrupt()

        checker = CreditChecker()
        with pytest.raises(KeyboardInterrupt):
            checker.check_key("sk-test-key")


class TestCheckKeys:
    """Tests for check_keys method."""

    @respx.mock
    def test_checks_multiple_keys(self):
        """Returns CreditInfo for each key."""
        route = respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "available_balance": 50.00,
                        "total_usage": 10.00,
                        "currency": "CNY",
                    }
                },
            )
        )

        checker = CreditChecker()
        results = checker.check_keys(["sk-key1", "sk-key2"])

        assert len(results) == 2
        assert route.call_count == 2
        assert all(r.balance == 50.00 for r in results)

    def test_empty_list_returns_empty(self):
        """Returns empty list for empty input."""
        checker = CreditChecker()
        results = checker.check_keys([])

        assert results == []


class TestGetPoolSummary:
    """Tests for get_pool_summary method."""

    @respx.mock
    def test_summary_with_valid_keys(self):
        """Returns aggregated summary."""
        respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "available_balance": 50.00,
                        "total_usage": 10.00,
                        "currency": "CNY",
                    }
                },
            )
        )

        checker = CreditChecker()
        summary = checker.get_pool_summary(["sk-key1", "sk-key2"])

        assert summary["total_keys"] == 2
        assert summary["valid_keys"] == 2
        assert summary["invalid_keys"] == 0
        assert summary["total_balance"] == 100.00
        assert summary["total_usage"] == 20.00
        assert summary["currency"] == "CNY"
        assert len(summary["keys"]) == 2

    @respx.mock
    def test_summary_with_mixed_validity(self):
        """Handles mix of valid and invalid keys."""
        route = respx.get(f"{KIMI_API_BASE}/v1/users/me/balance")
        route.side_effect = [
            Response(
                200,
                json={
                    "data": {
                        "available_balance": 50.00,
                        "total_usage": 10.00,
                    }
                },
            ),
            Response(401, json={"error": "Unauthorized"}),
        ]

        checker = CreditChecker()
        summary = checker.get_pool_summary(["sk-valid", "sk-invalid"])

        assert summary["total_keys"] == 2
        assert summary["valid_keys"] == 1
        assert summary["invalid_keys"] == 1
        assert summary["total_balance"] == 50.00

    @respx.mock
    def test_summary_with_all_invalid(self):
        """Handles all invalid keys."""
        respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(401, json={"error": "Unauthorized"})
        )

        checker = CreditChecker()
        summary = checker.get_pool_summary(["sk-key1", "sk-key2"])

        assert summary["total_keys"] == 2
        assert summary["valid_keys"] == 0
        assert summary["invalid_keys"] == 2
        assert summary["total_balance"] == 0.0
        assert summary["total_usage"] == 0.0

    def test_empty_pool_summary(self):
        """Summary for empty pool."""
        checker = CreditChecker()
        summary = checker.get_pool_summary([])

        assert summary["total_keys"] == 0
        assert summary["valid_keys"] == 0
        assert summary["invalid_keys"] == 0
        assert summary["total_balance"] == 0.0
        assert summary["total_usage"] == 0.0
        assert summary["keys"] == []


class TestCheckKeyCredits:
    """Tests for check_key_credits convenience function."""

    @respx.mock
    def test_convenience_function(self):
        """Returns summary using default checker."""
        respx.get(f"{KIMI_API_BASE}/v1/users/me/balance").mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "available_balance": 100.00,
                        "total_usage": 50.00,
                        "currency": "CNY",
                    }
                },
            )
        )

        summary = check_key_credits(["sk-test"])

        assert summary["total_keys"] == 1
        assert summary["total_balance"] == 100.00
