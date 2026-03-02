"""Tests for kimigas package initialization."""

from __future__ import annotations

import gasclaw.kimigas as kimigas


class TestPackageExports:
    """Tests for kimigas package-level exports."""

    def test_key_pool_exported(self):
        """KeyPool class is exported from package."""
        assert hasattr(kimigas, "KeyPool")
        assert callable(kimigas.KeyPool)

    def test_rate_limit_cooldown_exported(self):
        """RATE_LIMIT_COOLDOWN constant is exported."""
        assert hasattr(kimigas, "RATE_LIMIT_COOLDOWN")
        assert isinstance(kimigas.RATE_LIMIT_COOLDOWN, int)

    def test_credit_checker_exported(self):
        """CreditChecker class is exported."""
        assert hasattr(kimigas, "CreditChecker")
        assert callable(kimigas.CreditChecker)

    def test_credit_info_exported(self):
        """CreditInfo dataclass is exported."""
        assert hasattr(kimigas, "CreditInfo")

    def test_check_key_credits_exported(self):
        """check_key_credits function is exported."""
        assert hasattr(kimigas, "check_key_credits")
        assert callable(kimigas.check_key_credits)

    def test_kimi_anthropic_base_url_exported(self):
        """KIMI_ANTHROPIC_BASE_URL constant is exported."""
        assert hasattr(kimigas, "KIMI_ANTHROPIC_BASE_URL")
        assert isinstance(kimigas.KIMI_ANTHROPIC_BASE_URL, str)

    def test_build_claude_env_exported(self):
        """build_claude_env function is exported."""
        assert hasattr(kimigas, "build_claude_env")
        assert callable(kimigas.build_claude_env)

    def test_all_exports_defined(self):
        """__all__ is defined and contains expected exports."""
        assert hasattr(kimigas, "__all__")
        assert "KeyPool" in kimigas.__all__
        assert "RATE_LIMIT_COOLDOWN" in kimigas.__all__
        assert "CreditChecker" in kimigas.__all__
        assert "CreditInfo" in kimigas.__all__
        assert "check_key_credits" in kimigas.__all__
        assert "KIMI_ANTHROPIC_BASE_URL" in kimigas.__all__
        assert "build_claude_env" in kimigas.__all__

    def test_all_is_list_of_strings(self):
        """__all__ is a list of strings."""
        assert isinstance(kimigas.__all__, list)
        assert all(isinstance(item, str) for item in kimigas.__all__)

    def test_module_docstring_exists(self):
        """Package has a module-level docstring."""
        assert kimigas.__doc__ is not None
        assert "KimiGas" in kimigas.__doc__

    def test_key_pool_can_be_instantiated(self):
        """KeyPool can be instantiated from package export."""
        pool = kimigas.KeyPool(keys=["sk-key1", "sk-key2"])
        assert pool is not None

    def test_credit_info_can_be_created(self):
        """CreditInfo can be created from package export."""
        info = kimigas.CreditInfo(key="sk-test", balance=100.0, total_used=50.0)
        assert info.key == "sk-test"
        assert info.balance == 100.0
        assert info.total_used == 50.0
