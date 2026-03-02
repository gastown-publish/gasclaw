"""Kimi API credit usage checker per key.

Queries Kimi API billing endpoints to check credit balance and usage per API key.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import httpx

KIMI_API_BASE = "https://api.kimi.com"
logger = logging.getLogger(__name__)

__all__ = ["CreditInfo", "CreditChecker", "check_key_credits"]


@dataclass
class CreditInfo:
    """Credit information for a single API key."""

    key: str  # masked key for identification
    balance: float | None = None  # remaining balance in CNY
    total_used: float | None = None  # total usage in CNY
    currency: str = "CNY"
    valid: bool = True  # key is valid and active
    error: str | None = None  # error message if query failed

    @property
    def key_hash(self) -> str:
        """Return masked key identifier (last 8 chars)."""
        return f"...{self.key[-8:]}" if len(self.key) > 8 else self.key


class CreditChecker:
    """Check credit usage for Kimi API keys."""

    def __init__(self, base_url: str = KIMI_API_BASE) -> None:
        self.base_url = base_url

    def _mask_key(self, key: str) -> str:
        """Return masked key for display (last 8 chars only)."""
        return f"...{key[-8:]}" if len(key) > 8 else key

    def check_key(self, api_key: str) -> CreditInfo:
        """Check credit for a single API key.

        Args:
            api_key: The Kimi API key to check.

        Returns:
            CreditInfo with balance and usage data.

        """
        masked = self._mask_key(api_key)

        # Kimi API v1 billing endpoint
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                # Query user/balance endpoint
                response = client.get(
                    f"{self.base_url}/v1/users/me/balance",
                    headers=headers,
                )

                if response.status_code == 401:
                    return CreditInfo(
                        key=masked,
                        valid=False,
                        error="Invalid API key",
                    )

                if response.status_code == 429:
                    return CreditInfo(
                        key=masked,
                        valid=True,
                        error="Rate limited - try again later",
                    )

                response.raise_for_status()
                data: dict[str, Any] = response.json()

                # Kimi API returns balance in yuan/cents
                balance = data.get("data", {}).get("available_balance")
                total_used = data.get("data", {}).get("total_usage")
                currency = data.get("data", {}).get("currency", "CNY")

                return CreditInfo(
                    key=masked,
                    balance=_parse_amount(balance),
                    total_used=_parse_amount(total_used),
                    currency=currency,
                    valid=True,
                )

        except httpx.HTTPStatusError as e:
            logger.warning("HTTP error checking key %s: %s", masked, e.response.status_code)
            return CreditInfo(
                key=masked,
                valid=False,
                error=f"HTTP {e.response.status_code}",
            )
        except httpx.RequestError as e:
            logger.warning("Request error checking key %s: %s", masked, e)
            return CreditInfo(
                key=masked,
                valid=False,
                error=f"Request failed: {e}",
            )
        except Exception as e:
            logger.warning("Error checking key %s: %s", masked, e)
            return CreditInfo(
                key=masked,
                valid=False,
                error=str(e),
            )

    def check_keys(self, api_keys: list[str]) -> list[CreditInfo]:
        """Check credits for multiple API keys.

        Args:
            api_keys: List of Kimi API keys to check.

        Returns:
            List of CreditInfo for each key.

        """
        return [self.check_key(key) for key in api_keys]

    def get_pool_summary(self, api_keys: list[str]) -> dict[str, Any]:
        """Get aggregated credit summary for a key pool.

        Args:
            api_keys: List of Kimi API keys.

        Returns:
            Dict with total balance, usage, and per-key details.

        """
        results = self.check_keys(api_keys)

        valid_keys = [r for r in results if r.valid and r.balance is not None]
        invalid_keys = [r for r in results if not r.valid or r.balance is None]

        total_balance = sum(r.balance for r in valid_keys if r.balance)
        total_usage = sum(r.total_used for r in valid_keys if r.total_used)

        return {
            "total_keys": len(api_keys),
            "valid_keys": len(valid_keys),
            "invalid_keys": len(invalid_keys),
            "total_balance": total_balance,
            "total_usage": total_usage,
            "currency": "CNY",
            "keys": [
                {
                    "key": r.key_hash,
                    "balance": r.balance,
                    "total_used": r.total_used,
                    "valid": r.valid,
                    "error": r.error,
                }
                for r in results
            ],
        }


def _parse_amount(amount: Any) -> float | None:
    """Parse amount from API response."""
    if amount is None:
        return None
    try:
        result = float(amount)
        # Reject inf and nan as they're not valid amounts
        if math.isinf(result) or math.isnan(result):
            return None
        return round(result, 2)
    except (ValueError, TypeError):
        return None


def check_key_credits(api_keys: list[str]) -> dict[str, Any]:
    """Convenience function to check credits for a list of keys.

    Args:
        api_keys: List of Kimi API keys.

    Returns:
        Aggregated credit summary.

    """
    checker = CreditChecker()
    return checker.get_pool_summary(api_keys)
