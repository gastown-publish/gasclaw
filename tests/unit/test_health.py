"""Tests for gasclaw.health."""

from __future__ import annotations

import subprocess

from gasclaw.health import HealthReport, check_agent_activity, check_health


class TestCheckHealth:
    def test_report_structure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        report = check_health(gateway_port=18789)
        assert isinstance(report, HealthReport)
        assert hasattr(report, "dolt")
        assert hasattr(report, "daemon")
        assert hasattr(report, "mayor")
        assert hasattr(report, "openclaw")
        assert hasattr(report, "agents")
        assert hasattr(report, "key_pool")

    def test_all_healthy(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"running"),
        )
        report = check_health(gateway_port=18789)
        assert report.dolt == "healthy"
        assert report.daemon == "healthy"
        assert report.mayor == "healthy"

    def test_dolt_down(self, monkeypatch):
        def _mock_run(cmd, **kw):
            if "dolt" in str(cmd):
                return subprocess.CompletedProcess(cmd, 1, stderr=b"refused")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        monkeypatch.setattr(subprocess, "run", _mock_run)
        report = check_health(gateway_port=18789)
        assert report.dolt == "unhealthy"

    def test_agents_listed(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                a[0], 0, stdout=b"mayor\ndeacon\nwitness\ncrew-1\ncrew-2\n"
            ),
        )
        report = check_health(gateway_port=18789)
        assert isinstance(report.agents, list)


class TestCheckAgentActivity:
    def test_returns_activity_report(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                a[0], 0, stdout=b"1234567890\n"
            ),
        )
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=3600)
        assert "last_commit_age" in activity
        assert "compliant" in activity

    def test_no_recent_activity_flagged(self, monkeypatch):
        # No git log output — no recent commits
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b""),
        )
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=3600)
        assert activity["compliant"] is False

    def test_uses_project_dir(self, monkeypatch):
        calls = []
        def _capture(cmd, **kw):
            calls.append(kw.get("cwd"))
            return subprocess.CompletedProcess(cmd, 0, stdout=b"1234567890\n")
        monkeypatch.setattr(subprocess, "run", _capture)
        check_agent_activity(project_dir="/custom/path", deadline_seconds=3600)
        assert calls == ["/custom/path"]


class TestHealthReportSummary:
    def test_summary_string(self):
        report = HealthReport(
            dolt="healthy",
            daemon="healthy",
            mayor="healthy",
            openclaw="healthy",
            agents=["mayor", "crew-1"],
            key_pool={"total": 3, "available": 2, "rate_limited": 1},
            activity={"compliant": True, "last_commit_age": 600},
        )
        summary = report.summary()
        assert "healthy" in summary.lower()
        assert "mayor" in summary.lower() or "2 agents" in summary.lower()
