"""Tests for kimigas.credit_checker module."""

from __future__ import annotations

import httpx
import respx

from gasclaw.kimigas.credit_checker import (
    CreditChecker,
    CreditInfo,
    check_key_credits,
)


class TestCreditInfo:
    def test_key_hash_masks_key(self):
        """Key hash returns masked identifier."""
        info = CreditInfo(key="sk-test-key-1234abcd")
        assert info.key_hash == "...1234abcd"

    def test_key_hash_short_key(self):
        """Short key returns as-is."""
        info = CreditInfo(key="short")
        assert info.key_hash == "short"

    def test_default_values(self):
        """CreditInfo has sensible defaults."""
        info = CreditInfo(key="test")
        assert info.balance is None
        assert info.total_used is None
        assert info.currency == "CNY"
        assert info.valid is True
        assert info.error is None


class TestCreditChecker:
    def test_mask_key(self):
        """Key masking shows only last 8 chars."""
        checker = CreditChecker()
        masked = checker._mask_key("sk-test-key-1234abcd")
        assert masked == "...1234abcd"

    def test_mask_key_short(self):
        """Short key returns as-is."""
        checker = CreditChecker()
        masked = checker._mask_key("short")
        assert masked == "short"

    @respx.mock
    def test_check_key_success(self):
        """Successful credit check returns CreditInfo."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "available_balance": 100.0,
                        "total_usage": 50.0,
                        "currency": "CNY",
                    }
                },
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is True
        assert result.balance == 100.0
        assert result.total_used == 50.0
        assert result.currency == "CNY"
        assert route.called

    @respx.mock
    def test_check_key_invalid_auth(self):
        """401 response returns invalid CreditInfo."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(401, json={"error": "Unauthorized"})
        )

        checker = CreditChecker()
        result = checker.check_key("sk-invalid-key")

        assert result.valid is False
        assert result.error == "Invalid API key"
        assert route.called

    @respx.mock
    def test_check_key_rate_limited(self):
        """429 response returns rate limited info."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(429, json={"error": "Rate limited"})
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is True  # key is still valid
        assert "Rate limited" in result.error
        assert route.called

    @respx.mock
    def test_check_key_server_error(self):
        """500 response returns error info."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert "HTTP 500" in result.error
        assert route.called

    @respx.mock
    def test_check_key_network_error(self):
        """Network error returns error info."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert "Request failed" in result.error
        assert route.called

    @respx.mock
    def test_check_keys_multiple(self):
        """Check multiple keys returns list of CreditInfo."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"available_balance": 50.0, "total_usage": 10.0}},
            )
        )

        checker = CreditChecker()
        results = checker.check_keys(["sk-key1", "sk-key2"])

        assert len(results) == 2
        assert all(r.valid for r in results)
        assert route.call_count == 2

    @respx.mock
    def test_get_pool_summary(self):
        """Pool summary aggregates key data."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance")
        route.side_effect = [
            httpx.Response(
                200,
                json={"data": {"available_balance": 100.0, "total_usage": 50.0}},
            ),
            httpx.Response(
                200,
                json={"data": {"available_balance": 200.0, "total_usage": 100.0}},
            ),
        ]

        checker = CreditChecker()
        summary = checker.get_pool_summary(["sk-key1", "sk-key2"])

        assert summary["total_keys"] == 2
        assert summary["valid_keys"] == 2
        assert summary["invalid_keys"] == 0
        assert summary["total_balance"] == 300.0  # 100 + 200
        assert summary["total_usage"] == 150.0  # 50 + 100
        assert len(summary["keys"]) == 2

    @respx.mock
    def test_get_pool_summary_with_invalid_key(self):
        """Pool summary handles mix of valid and invalid keys."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance")
        route.side_effect = [
            httpx.Response(
                200,
                json={"data": {"available_balance": 100.0, "total_usage": 50.0}},
            ),
            httpx.Response(401, json={"error": "Unauthorized"}),
        ]

        checker = CreditChecker()
        summary = checker.get_pool_summary(["sk-valid", "sk-invalid"])

        assert summary["total_keys"] == 2
        assert summary["valid_keys"] == 1
        assert summary["invalid_keys"] == 1
        assert summary["total_balance"] == 100.0

    @respx.mock
    def test_yuan_amount_not_converted(self):
        """Yuan amounts (small numbers) are not converted."""
        respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"available_balance": 50.5, "total_usage": 10.25}},
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test")

        # Small amounts (< 10000) are treated as yuan
        assert result.balance == 50.5
        assert result.total_used == 10.25

    @respx.mock
    def test_large_amount_not_converted(self):
        """Large amounts are preserved as-is (no conversion)."""
        respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"available_balance": 1234567, "total_usage": 890123}},
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test")

        # Amounts are preserved as-is from API
        assert result.balance == 1234567.0
        assert result.total_used == 890123.0

    @respx.mock
    def test_none_amount_handled(self):
        """None amounts are handled gracefully."""
        respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"available_balance": None, "total_usage": None}},
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test")

        assert result.balance is None
        assert result.total_used is None


class TestCheckKeyCredits:
    """Tests for the convenience function."""

    @respx.mock
    def test_check_key_credits(self):
        """Convenience function returns summary."""
        route = respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"available_balance": 100.0, "total_usage": 50.0}},
            )
        )

        summary = check_key_credits(["sk-key1"])

        assert summary["total_keys"] == 1
        assert summary["valid_keys"] == 1
        assert route.called


class TestCheckKeyGenericException:
    """Tests for generic exception handling in check_key (lines 116-118)."""

    def test_check_key_generic_exception(self, monkeypatch):
        """check_key handles unexpected exceptions (covers lines 116-118)."""

        def raise_exception(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        monkeypatch.setattr(httpx.Client, "__enter__", raise_exception)

        checker = CreditChecker()
        result = checker.check_key("sk-test-key")

        assert result.valid is False
        assert "Unexpected error" in result.error


class TestPoolSummaryEdgeCases:
    """Tests for pool summary edge cases."""

    @respx.mock
    def test_valid_key_with_none_balance_counts_as_invalid(self):
        """Keys with valid=True but balance=None should be counted as invalid.

        This tests the fix for a bug where keys with no balance data were
        not being properly counted in either valid or invalid categories.
        """
        route = respx.get("https://api.kimi.com/v1/users/me/balance")
        route.side_effect = [
            # First key: valid with balance
            httpx.Response(
                200,
                json={"data": {"available_balance": 100.0, "total_usage": 50.0}},
            ),
            # Second key: valid response but no balance data (None)
            httpx.Response(
                200,
                json={"data": {"available_balance": None, "total_usage": None}},
            ),
            # Third key: explicitly invalid (401)
            httpx.Response(401, json={"error": "Unauthorized"}),
        ]

        checker = CreditChecker()
        summary = checker.get_pool_summary(["sk-valid", "sk-no-balance", "sk-invalid"])

        assert summary["total_keys"] == 3
        assert summary["valid_keys"] == 1  # Only sk-valid
        assert summary["invalid_keys"] == 2  # sk-no-balance AND sk-invalid
        assert summary["total_balance"] == 100.0


class TestParseAmountEdgeCases:
    """Tests for _parse_amount edge cases (lines 178-179)."""

    @respx.mock
    def test_parse_amount_valueerror(self):
        """_parse_amount handles ValueError for invalid amounts (covers lines 178-179)."""
        # Mock response with non-numeric balance that causes ValueError
        respx.get("https://api.kimi.com/v1/users/me/balance").mock(
            return_value=httpx.Response(
                200,
                json={"data": {"available_balance": "invalid", "total_usage": "not-a-number"}},
            )
        )

        checker = CreditChecker()
        result = checker.check_key("sk-test")

        # Should not crash - returns None for invalid amounts
        assert result.balance is None
        assert result.total_used is None
        assert result.valid is True
