"""Tests for gasclaw.updater.applier."""

from __future__ import annotations

import subprocess

from gasclaw.updater.applier import apply_updates


class TestApplyUpdates:
    def test_runs_update_commands(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        apply_updates()
        assert len(calls) > 0
        # Should attempt to update gt, openclaw, kimigas
        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        assert any("gt" in s for s in cmd_strs)

    def test_handles_failures(self, monkeypatch):
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"fail"),
        )
        results = apply_updates()
        assert any("failed" in v.lower() or "error" in v.lower() for v in results.values())

    def test_handles_timeout(self, monkeypatch):
        """TimeoutExpired is caught and reported."""

        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0], timeout=120)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        results = apply_updates()
        assert any("error" in v.lower() or "timeout" in v.lower() for v in results.values())

    def test_handles_missing_binary(self, monkeypatch):
        """FileNotFoundError is caught and reported."""

        def raise_not_found(*a, **kw):
            raise FileNotFoundError("gt not found")

        monkeypatch.setattr(subprocess, "run", raise_not_found)
        results = apply_updates()
        assert any("error" in v.lower() or "not found" in v.lower() for v in results.values())

    def test_stderr_truncation_on_failure(self, monkeypatch):
        """Long stderr is truncated to 200 chars."""
        long_error = b"x" * 500
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=long_error),
        )
        results = apply_updates()
        # Check that no error message exceeds reasonable length
        for v in results.values():
            if "failed:" in v:
                # The error portion after "failed: " should be truncated
                error_part = v.split("failed: ", 1)[1]
                assert len(error_part) <= 200
