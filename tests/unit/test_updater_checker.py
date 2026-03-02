"""Tests for gasclaw.updater.checker."""

from __future__ import annotations

import logging
import subprocess

from gasclaw.updater.checker import check_versions


class TestCheckVersions:
    def test_returns_version_dict(self, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"1.0.0\n"),
        )
        versions = check_versions()
        assert "gt" in versions
        assert "claude" in versions
        assert "openclaw" in versions
        assert "dolt" in versions

    def test_handles_missing_binary(self, monkeypatch):
        def _fail(*a, **kw):
            raise FileNotFoundError("not found")

        monkeypatch.setattr(subprocess, "run", _fail)
        versions = check_versions()
        for v in versions.values():
            assert v == "not installed"

    def test_handles_nonzero_exit(self, monkeypatch):
        """Non-zero exit code is treated as not installed."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stdout=b"", stderr=b"error"),
        )
        versions = check_versions()
        for v in versions.values():
            assert v == "not installed"

    def test_handles_timeout(self, monkeypatch):
        """TimeoutExpired is caught and reported as not installed."""

        def _timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0], timeout=10)

        monkeypatch.setattr(subprocess, "run", _timeout)
        versions = check_versions()
        for v in versions.values():
            assert v == "not installed"

    def test_strips_whitespace_from_output(self, monkeypatch):
        """Version output has whitespace stripped."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"  1.0.0  \n\r\n"),
        )
        versions = check_versions()
        for v in versions.values():
            assert v == "1.0.0"

    def test_includes_kimigas(self, monkeypatch):
        """Kimigas is included in version checks."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"0.5.0\n"),
        )
        versions = check_versions()
        assert "kimigas" in versions
        assert versions["kimigas"] == "0.5.0"


class TestCheckerLogging:
    """Tests for logging in version checker."""

    def test_logs_debug_on_success(self, monkeypatch, caplog):
        """Successful version check logs debug message."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"1.0.0\n"),
        )

        with caplog.at_level(logging.DEBUG):
            check_versions()

        assert "version:" in caplog.text.lower()

    def test_logs_warning_on_nonzero_exit(self, monkeypatch, caplog):
        """Non-zero exit code logs warning."""
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stdout=b"", stderr=b"error"),
        )

        with caplog.at_level(logging.WARNING):
            check_versions()

        assert "non-zero exit code" in caplog.text.lower()

    def test_logs_warning_on_timeout(self, monkeypatch, caplog):
        """Timeout logs warning."""
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0], timeout=10)

        monkeypatch.setattr(subprocess, "run", raise_timeout)

        with caplog.at_level(logging.WARNING):
            check_versions()

        assert "timed out" in caplog.text.lower()
