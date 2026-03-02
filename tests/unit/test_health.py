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


class TestCheckServiceErrorHandling:
    """Tests for _check_service() exception handling."""

    def test_check_service_file_not_found(self, monkeypatch):
        """Test _check_service returns 'unhealthy' when command is not found."""
        from gasclaw.health import _check_service

        def _raise_filenotfound(*a, **kw):
            raise FileNotFoundError("command not found")

        monkeypatch.setattr(subprocess, "run", _raise_filenotfound)
        result = _check_service(["gt", "daemon", "status"], "daemon")
        assert result == "unhealthy"

    def test_check_service_timeout_expired(self, monkeypatch):
        """Test _check_service returns 'unhealthy' when command times out."""
        from gasclaw.health import _check_service

        def _raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0] if a else "cmd", timeout=10)

        monkeypatch.setattr(subprocess, "run", _raise_timeout)
        result = _check_service(["gt", "daemon", "status"], "daemon")
        assert result == "unhealthy"

    def test_git_error_returns_non_compliant(self, monkeypatch):
        """Git command failure returns non-compliant activity."""
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"not a git repo"),
        )
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None

    def test_invalid_timestamp_returns_non_compliant(self, monkeypatch):
        """Invalid timestamp in git output returns non-compliant."""
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"not-a-number\n"),
        )
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=3600)
        assert activity["compliant"] is False

    def test_file_not_found_returns_non_compliant(self, monkeypatch):
        """FileNotFoundError (git not installed) returns non-compliant."""
        def raise_not_found(*a, **kw):
            raise FileNotFoundError("git not found")
        monkeypatch.setattr(subprocess, "run", raise_not_found)
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None

    def test_timeout_returns_non_compliant(self, monkeypatch):
        """TimeoutExpired returns non-compliant."""
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0], timeout=10)
        monkeypatch.setattr(subprocess, "run", raise_timeout)
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None


class TestListAgentsErrorHandling:
    """Tests for _list_agents() exception handling."""

    def test_list_agents_file_not_found(self, monkeypatch):
        """Test _list_agents returns empty list when gt command is not found."""
        from gasclaw.health import _list_agents

        def _raise_filenotfound(*a, **kw):
            raise FileNotFoundError("gt command not found")

        monkeypatch.setattr(subprocess, "run", _raise_filenotfound)
        result = _list_agents()
        assert result == []

    def test_list_agents_timeout_expired(self, monkeypatch):
        """Test _list_agents returns empty list when gt status times out."""
        from gasclaw.health import _list_agents

        def _raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0] if a else "cmd", timeout=10)

        monkeypatch.setattr(subprocess, "run", _raise_timeout)
        result = _list_agents()
        assert result == []


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

    def test_summary_with_empty_agents(self):
        """Summary handles empty agents list."""
        report = HealthReport(
            dolt="healthy",
            agents=[],
            key_pool={"total": 1, "available": 1},
        )
        summary = report.summary()
        assert "0 active" in summary or "agents:" in summary.lower()

    def test_summary_with_no_activity(self):
        """Summary handles missing activity data."""
        report = HealthReport(
            dolt="healthy",
            agents=["mayor"],
            key_pool={"total": 1, "available": 1},
            activity={},
        )
        summary = report.summary()
        # Should not mention activity when empty
        assert "compliant" not in summary.lower()

    def test_summary_with_unhealthy_services(self):
        """Summary shows unhealthy services correctly."""
        report = HealthReport(
            dolt="unhealthy",
            daemon="unhealthy",
            mayor="healthy",
            agents=["mayor"],
            key_pool={"total": 2, "available": 1},
        )
        summary = report.summary()
        assert "unhealthy" in summary.lower()

    def test_summary_with_missing_key_pool(self):
        """Summary handles missing or empty key_pool data."""
        report = HealthReport(
            dolt="healthy",
            agents=["mayor"],
            key_pool={},
        )
        summary = report.summary()
        assert "?" in summary  # Should show ? for unknown values

    def test_summary_with_none_activity_age(self):
        """Summary handles None last_commit_age in activity."""
        report = HealthReport(
            dolt="healthy",
            agents=["mayor"],
            key_pool={"total": 1, "available": 1},
            activity={"compliant": False, "last_commit_age": None},
        )
        summary = report.summary()
        assert "not compliant" in summary.lower() or "?" in summary

    def test_summary_with_many_agents_truncated(self):
        """Summary truncates agent list when many agents."""
        report = HealthReport(
            dolt="healthy",
            agents=[f"agent-{i}" for i in range(10)],
            key_pool={"total": 10, "available": 10},
        )
        summary = report.summary()
        assert "10 active" in summary or "agents:" in summary.lower()

    def test_summary_shows_openclaw_doctor_status(self):
        """Summary includes OpenClaw Doctor status."""
        report = HealthReport(
            dolt="healthy",
            openclaw_doctor="healthy",
            agents=["mayor"],
            key_pool={"total": 1, "available": 1},
        )
        summary = report.summary()
        assert "Doctor" in summary or "openclaw" in summary.lower()


class TestHealthCheckEdgeCases:
    def test_check_health_with_timeout_expired(self, monkeypatch):
        """check_health handles TimeoutExpired gracefully."""
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0], timeout=10)
        monkeypatch.setattr(subprocess, "run", raise_timeout)
        report = check_health(gateway_port=18789)
        # Should return report with unhealthy status, not raise
        assert report.dolt == "unhealthy"
        assert report.daemon == "unhealthy"

    def test_check_health_agents_with_file_not_found(self, monkeypatch):
        """_list_agents handles FileNotFoundError when gt not installed."""
        def mock_run(cmd, **kw):
            if "status" in str(cmd) and "--agents" in str(cmd):
                raise FileNotFoundError("gt not found")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        monkeypatch.setattr(subprocess, "run", mock_run)
        report = check_health(gateway_port=18789)
        assert report.agents == []

    def test_check_health_agents_with_timeout(self, monkeypatch):
        """_list_agents handles TimeoutExpired gracefully."""
        def mock_run(cmd, **kw):
            if "status" in str(cmd) and "--agents" in str(cmd):
                raise subprocess.TimeoutExpired(cmd=["gt"], timeout=10)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        monkeypatch.setattr(subprocess, "run", mock_run)
        report = check_health(gateway_port=18789)
        assert report.agents == []

    def test_check_agent_activity_zero_deadline(self, monkeypatch):
        """check_agent_activity with zero deadline requires recent commits."""
        import time
        # Use current timestamp so age is approximately 0
        now_ts = int(time.time())
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                a[0], 0, stdout=f"{now_ts}\n".encode()
            ),
        )
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=0)
        # Age should be 0 (or close to it), so 0 <= 0 is True
        assert activity["compliant"] is True
        assert activity["last_commit_age"] <= 1  # Should be very recent

    def test_check_agent_activity_very_large_deadline(self, monkeypatch):
        """check_agent_activity with very large deadline accepts old commits."""
        import time
        old_timestamp = int(time.time()) - 86400  # 1 day ago
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                a[0], 0, stdout=f"{old_timestamp}\n".encode()
            ),
        )
        activity = check_agent_activity(project_dir="/tmp/test", deadline_seconds=100000)
        assert activity["compliant"] is True

    def test_check_health_custom_gateway_port(self, monkeypatch):
        """check_health uses custom gateway port for openclaw check."""
        calls = []
        def mock_run(cmd, **kw):
            calls.append(str(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")
        monkeypatch.setattr(subprocess, "run", mock_run)
        check_health(gateway_port=99999)
        # Check that custom port appears in curl command
        assert any("99999" in c for c in calls)
