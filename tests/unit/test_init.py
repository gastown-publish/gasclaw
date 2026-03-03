"""Tests for gasclaw package initialization."""

from __future__ import annotations

import gasclaw


class TestPackageMetadata:
    """Tests for package-level metadata."""

    def test_version_matches_expected(self):
        """Package version is correctly set."""
        assert gasclaw.__version__ == "0.2.0"

    def test_version_is_string(self):
        """Version is a string (not a tuple or other type)."""
        assert isinstance(gasclaw.__version__, str)

    def test_module_docstring_exists(self):
        """Package has a module-level docstring."""
        assert gasclaw.__doc__ is not None
        assert "Gasclaw" in gasclaw.__doc__

    def test_docstring_contains_components(self):
        """Docstring mentions the key components."""
        assert "Gastown" in gasclaw.__doc__
        assert "OpenClaw" in gasclaw.__doc__
        assert "KimiGas" in gasclaw.__doc__

    def test_all_exports_defined(self):
        """__all__ is defined and contains expected exports."""
        assert hasattr(gasclaw, "__all__")
        assert "__version__" in gasclaw.__all__
        assert "bootstrap" in gasclaw.__all__
        assert "load_config" in gasclaw.__all__

    def test_all_is_list_of_strings(self):
        """__all__ is a list of strings."""
        assert isinstance(gasclaw.__all__, list)
        assert all(isinstance(item, str) for item in gasclaw.__all__)

    def test_module_is_importable(self):
        """Module can be imported without errors."""
        # This test passes if we got here - the import worked
        assert gasclaw is not None

    def test_docstring_has_example(self):
        """Docstring includes usage example."""
        assert "Example:" in gasclaw.__doc__
        assert "load_config" in gasclaw.__doc__
        assert "bootstrap" in gasclaw.__doc__

    def test_bootstrap_exported(self):
        """bootstrap function is exported from package."""
        assert hasattr(gasclaw, "bootstrap")
        assert callable(gasclaw.bootstrap)

    def test_load_config_exported(self):
        """load_config function is exported from package."""
        assert hasattr(gasclaw, "load_config")
        assert callable(gasclaw.load_config)
