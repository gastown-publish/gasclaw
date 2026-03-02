"""Tests for gasclaw.updater.applier."""

from __future__ import annotations

import subprocess

from gasclaw.updater.applier import apply_updates


class TestApplyUpdates:
    def test_runs_update_commands(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: calls.append(a[0]) or subprocess.CompletedProcess(a[0], 0),
        )
        apply_updates()
        assert len(calls) > 0
        # Should attempt to update gt, openclaw, kimigas
        cmd_strs = [" ".join(str(x) for x in cmd) for cmd in calls]
        assert any("gt" in s for s in cmd_strs)

    def test_handles_failures(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"fail"),
        )
        results = apply_updates()
        assert any("failed" in v.lower() or "error" in v.lower() for v in results.values())
