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