"""Integration tests for gasclaw.health.

These tests verify health checks work correctly with mocked subprocess calls
and HTTP dependencies.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest
import respx
from httpx import Response

from gasclaw.health import HealthReport, check_agent_activity, check_health


class TestHealthCheckIntegration:
    """Integration tests for health check system."""

    def test_full_health_report_with_all_services_healthy(self, monkeypatch):
        """Test complete health report when all services are healthy."""
        def mock_subprocess_run(cmd, **kwargs):
            # Return success for all service checks
            return subprocess.CompletedProcess(cmd, 0, stdout=b"running", stderr=b"")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        with patch("gasclaw.health.run_doctor") as mock_doctor:
            mock_doctor.return_value = MagicMock(healthy=True, returncode=0, output="OK")
            
            report = check_health(gateway_port=18789)
        
        assert isinstance(report, HealthReport)
        assert report.dolt == "healthy"
        assert report.daemon == "healthy"
        assert report.mayor == "healthy"
        assert report.openclaw == "healthy"
        assert report.openclaw_doctor == "healthy"

    def test_health_report_with_mixed_service_status(self, monkeypatch):
        """Test health report with some services up, some down."""
        def mock_subprocess_run(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            
            if "dolt" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")  # Healthy
            elif "daemon" in cmd_str:
                return subprocess.CompletedProcess(cmd, 1, stderr=b"not running")  # Unhealthy
            elif "mayor" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")  # Healthy
            elif "curl" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=b"healthy")  # Healthy
            elif "gt status" in cmd_str:
                return subprocess.CompletedProcess(cmd, 0, stdout=b"mayor\n")
            
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        with patch("gasclaw.health.run_doctor") as mock_doctor:
            mock_doctor.return_value = MagicMock(healthy=True, returncode=0, output="OK")
            
            report = check_health(gateway_port=18789)
        
        assert report.dolt == "healthy"
        assert report.daemon == "unhealthy"
        assert report.mayor == "healthy"
        assert report.openclaw == "healthy"
        assert "mayor" in report.agents

    def test_health_report_with_doctor_failure(self, monkeypatch):
        """Test health report when openclaw doctor fails."""
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok")
        )
        
        with patch("gasclaw.health.run_doctor") as mock_doctor:
            mock_doctor.return_value = MagicMock(
                healthy=False, 
                returncode=1, 
                output="Missing config"
            )
            
            report = check_health(gateway_port=18789)
        
        assert report.openclaw_doctor == "unhealthy"

    def test_health_report_with_gateway_timeout(self, monkeypatch):
        """Test health report when gateway check times out."""
        def mock_subprocess_run(cmd, **kwargs):
            if "curl" in str(cmd):
                raise subprocess.TimeoutExpired(cmd, 10)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        with patch("gasclaw.health.run_doctor") as mock_doctor:
            mock_doctor.return_value = MagicMock(healthy=True, returncode=0, output="OK")
            
            report = check_health(gateway_port=18789)
        
        assert report.openclaw == "unhealthy"

    def test_health_report_lists_multiple_agents(self, monkeypatch):
        """Test health report correctly lists multiple running agents."""
        agents_output = b"mayor\ndeacon\nwitness\ncrew-1\ncrew-2\ncrew-3\n"
        
        def mock_subprocess_run(cmd, **kwargs):
            if "gt status --agents" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=agents_output)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        with patch("gasclaw.health.run_doctor") as mock_doctor:
            mock_doctor.return_value = MagicMock(healthy=True, returncode=0, output="OK")
            
            report = check_health(gateway_port=18789)
        
        assert len(report.agents) == 6
        assert "mayor" in report.agents
        assert "deacon" in report.agents
        assert "witness" in report.agents

    def test_health_report_with_no_agents(self, monkeypatch):
        """Test health report handles no running agents."""
        def mock_subprocess_run(cmd, **kwargs):
            if "gt status --agents" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=b"")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        with patch("gasclaw.health.run_doctor") as mock_doctor:
            mock_doctor.return_value = MagicMock(healthy=True, returncode=0, output="OK")
            
            report = check_health(gateway_port=18789)
        
        assert report.agents == []

    def test_health_report_with_missing_commands(self, monkeypatch):
        """Test health report handles missing commands gracefully."""
        def mock_subprocess_run(cmd, **kwargs):
            if "dolt" in str(cmd):
                raise FileNotFoundError("dolt not found")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        with patch("gasclaw.health.run_doctor") as mock_doctor:
            mock_doctor.return_value = MagicMock(healthy=True, returncode=0, output="OK")
            
            report = check_health(gateway_port=18789)
        
        assert report.dolt == "unhealthy"


class TestAgentActivityIntegration:
    """Integration tests for agent activity checking."""

    def test_activity_check_with_recent_commit(self, monkeypatch):
        """Test activity check with recent git commit."""
        import time
        
        # Recent timestamp (5 minutes ago)
        recent_ts = int(time.time()) - 300
        
        def mock_subprocess_run(cmd, **kwargs):
            if "git log" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=str(recent_ts).encode())
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        activity = check_agent_activity(
            project_dir="/test/project",
            deadline_seconds=3600
        )
        
        assert activity["compliant"] is True
        assert activity["last_commit_age"] == 300

    def test_activity_check_with_old_commit(self, monkeypatch):
        """Test activity check with old git commit (non-compliant)."""
        import time
        
        # Old timestamp (2 hours ago)
        old_ts = int(time.time()) - 7200
        
        def mock_subprocess_run(cmd, **kwargs):
            if "git log" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=str(old_ts).encode())
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        activity = check_agent_activity(
            project_dir="/test/project",
            deadline_seconds=3600
        )
        
        assert activity["compliant"] is False
        assert activity["last_commit_age"] == 7200

    def test_activity_check_with_no_commits(self, monkeypatch):
        """Test activity check with no git history."""
        def mock_subprocess_run(cmd, **kwargs):
            if "git log" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=b"")  # No output
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        activity = check_agent_activity(
            project_dir="/test/project",
            deadline_seconds=3600
        )
        
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None

    def test_activity_check_uses_project_dir(self, monkeypatch):
        """Test activity check uses correct project directory."""
        captured_cwd = []
        
        def mock_subprocess_run(cmd, **kwargs):
            captured_cwd.append(kwargs.get("cwd"))
            if "git log" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=b"1234567890")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        check_agent_activity(
            project_dir="/custom/project/path",
            deadline_seconds=3600
        )
        
        assert captured_cwd == ["/custom/project/path"]

    def test_activity_check_with_git_error(self, monkeypatch):
        """Test activity check handles git errors gracefully."""
        def mock_subprocess_run(cmd, **kwargs):
            if "git log" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 128, stderr=b"fatal: not a git repository")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        activity = check_agent_activity(
            project_dir="/not/a/repo",
            deadline_seconds=3600
        )
        
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None

    def test_activity_check_with_invalid_timestamp(self, monkeypatch):
        """Test activity check handles invalid timestamp output."""
        def mock_subprocess_run(cmd, **kwargs):
            if "git log" in " ".join(str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=b"not-a-timestamp")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        activity = check_agent_activity(
            project_dir="/test/project",
            deadline_seconds=3600
        )
        
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None


class TestHealthReportSummary:
    """Integration tests for health report summary generation."""

    def test_summary_with_all_healthy(self):
        """Test summary generation for fully healthy system."""
        report = HealthReport(
            dolt="healthy",
            daemon="healthy",
            mayor="healthy",
            openclaw="healthy",
            openclaw_doctor="healthy",
            agents=["mayor", "deacon", "witness"],
            key_pool={"total": 5, "available": 4, "rate_limited": 1},
            activity={"compliant": True, "last_commit_age": 600},
        )
        
        summary = report.summary()
        
        assert "Dolt: healthy" in summary
        assert "Daemon: healthy" in summary
        assert "Mayor: healthy" in summary
        assert "OpenClaw: healthy" in summary
        assert "3 active" in summary
        assert "4/5 available" in summary
        assert "compliant" in summary.lower()

    def test_summary_with_issues(self):
        """Test summary generation with service issues."""
        report = HealthReport(
            dolt="unhealthy",
            daemon="healthy",
            mayor="unhealthy",
            openclaw="healthy",
            openclaw_doctor="unhealthy",
            agents=[],
            key_pool={"total": 3, "available": 0, "rate_limited": 3},
            activity={"compliant": False, "last_commit_age": 5000},
        )
        
        summary = report.summary()
        
        assert "Dolt: unhealthy" in summary
        assert "Mayor: unhealthy" in summary
        assert "0 active" in summary
        assert "0/3 available" in summary
        assert "NOT COMPLIANT" in summary

    def test_summary_with_empty_key_pool(self):
        """Test summary with empty or missing key pool data."""
        report = HealthReport(
            dolt="healthy",
            daemon="healthy",
            mayor="healthy",
            openclaw="healthy",
            agents=["mayor"],
            key_pool={},
            activity={},
        )
        
        summary = report.summary()
        
        assert "?/? available" in summary or "available" in summary

    def test_summary_with_many_agents(self):
        """Test summary truncates long agent lists."""
        report = HealthReport(
            dolt="healthy",
            daemon="healthy",
            mayor="healthy",
            openclaw="healthy",
            agents=[f"agent-{i}" for i in range(20)],
            key_pool={"total": 10, "available": 10},
            activity={"compliant": True, "last_commit_age": 100},
        )
        
        summary = report.summary()
        
        # Should show agent count
        assert "20 active" in summary or "agents" in summary.lower()
