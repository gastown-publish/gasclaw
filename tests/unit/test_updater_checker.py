"""Tests for gasclaw.updater.checker."""

from __future__ import annotations

import subprocess

from gasclaw.updater.checker import check_versions


class TestCheckVersions:
    def test_returns_version_dict(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                a[0], 0, stdout=b"1.0.0\n"
            ),
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
