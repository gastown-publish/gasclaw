"""Tests for gasclaw.health."""

from __future__ import annotations

import subprocess

import httpx
import respx

from gasclaw.health import HealthReport, check_agent_activity, check_health


class TestCheckHealth:
    def test_report_structure(self, monkeypatch, respx_mock: respx.MockRouter):
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))
        monkeypatch.setattr(
            subprocess,
            "run",
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

    def test_all_healthy(self, monkeypatch, respx_mock: respx.MockRouter):
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"running"),
        )
        report = check_health(gateway_port=18789)
        assert report.dolt == "healthy"
        assert report.daemon == "healthy"
        assert report.mayor == "healthy"
        assert report.openclaw == "healthy"

    def test_dolt_down(self, monkeypatch, respx_mock: respx.MockRouter):
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))

        def _mock_run(cmd, **kw):
            if "dolt" in str(cmd):
                return subprocess.CompletedProcess(cmd, 1, stderr=b"refused")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")

        monkeypatch.setattr(subprocess, "run", _mock_run)
        report = check_health(gateway_port=18789)
        assert report.dolt == "unhealthy"

    def test_custom_dolt_port(self, monkeypatch, respx_mock: respx.MockRouter):
        """Custom dolt_port is passed to the dolt command."""
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))

        captured_cmds = []

        def _mock_run(cmd, **kw):
            captured_cmds.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")

        monkeypatch.setattr(subprocess, "run", _mock_run)
        report = check_health(gateway_port=18789, dolt_port=3308)
        assert report.dolt == "healthy"
        # Check that dolt command used the custom port
        dolt_cmds = [c for c in captured_cmds if "dolt" in str(c)]
        assert len(dolt_cmds) == 1
        assert "3308" in dolt_cmds[0]

    def test_default_dolt_port(self, monkeypatch, respx_mock: respx.MockRouter):
        """Default dolt_port is 3307."""
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))

        captured_cmds = []

        def _mock_run(cmd, **kw):
            captured_cmds.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")

        monkeypatch.setattr(subprocess, "run", _mock_run)
        report = check_health(gateway_port=18789)
        assert report.dolt == "healthy"
        # Check that dolt command used the default port
        dolt_cmds = [c for c in captured_cmds if "dolt" in str(c)]
        assert len(dolt_cmds) == 1
        assert "3307" in dolt_cmds[0]

    def test_agents_listed(self, monkeypatch, respx_mock: respx.MockRouter):
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                a[0], 0, stdout=b"mayor\ndeacon\nwitness\ncrew-1\ncrew-2\n"
            ),
        )
        report = check_health(gateway_port=18789)
        assert isinstance(report.agents, list)


class TestCheckAgentActivityValidation:
    """Tests for check_agent_activity() project_dir validation."""

    def test_project_dir_not_exists_returns_error(self, tmp_path, monkeypatch):
        """Non-existent project_dir returns error when git fails."""
        non_existent_dir = str(tmp_path / "does_not_exist")

        # Mock git to fail (as it would for non-existent directory)
        def mock_git_fail(*a, **kw):
            return subprocess.CompletedProcess(a[0], 128, stderr=b"fatal: not a git repository")

        monkeypatch.setattr(subprocess, "run", mock_git_fail)
        activity = check_agent_activity(project_dir=non_existent_dir, deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None
        assert activity["error"] is not None

    def test_project_dir_is_file_not_directory(self, tmp_path, monkeypatch):
        """project_dir that is a file returns error when git fails."""
        file_path = tmp_path / "not_a_directory"
        file_path.write_text("I am a file")

        # Mock git to fail (as it would for invalid directory)
        def mock_git_fail(*a, **kw):
            return subprocess.CompletedProcess(a[0], 128, stderr=b"fatal: not a git repository")

        monkeypatch.setattr(subprocess, "run", mock_git_fail)
        activity = check_agent_activity(project_dir=str(file_path), deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None
        assert activity["error"] is not None

    def test_project_dir_not_git_repo_returns_error(self, tmp_path, monkeypatch):
        """Directory without .git returns error when git fails."""
        non_git_dir = tmp_path / "not_a_git_repo"
        non_git_dir.mkdir()

        # Mock git to fail (as it would for non-git directory)
        def mock_git_fail(*a, **kw):
            return subprocess.CompletedProcess(a[0], 128, stderr=b"fatal: not a git repository")

        monkeypatch.setattr(subprocess, "run", mock_git_fail)
        activity = check_agent_activity(project_dir=str(non_git_dir), deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None
        assert activity["error"] is not None

    def test_valid_git_repo_returns_success(self, tmp_path, monkeypatch):
        """Valid git repository returns compliant status."""
        import time

        git_dir = tmp_path / "valid_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        # Mock git log to return current timestamp
        now_ts = int(time.time())
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=f"{now_ts}\n".encode()),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        assert activity["compliant"] is True
        assert activity["last_commit_age"] is not None
        assert activity["error"] is None


class TestCheckOpenclawGateway:
    """Tests for _check_openclaw_gateway() function."""

    def test_returns_healthy_on_200(self, respx_mock: respx.MockRouter):
        """Returns healthy when gateway returns 200."""
        from gasclaw.health import _check_openclaw_gateway

        respx_mock.get("http://localhost:8080/health").mock(return_value=httpx.Response(200))
        result = _check_openclaw_gateway(8080)
        assert result == "healthy"

    def test_returns_unhealthy_on_503(self, respx_mock: respx.MockRouter):
        """Returns unhealthy when gateway returns 503."""
        from gasclaw.health import _check_openclaw_gateway

        respx_mock.get("http://localhost:8080/health").mock(return_value=httpx.Response(503))
        result = _check_openclaw_gateway(8080)
        assert result == "unhealthy"

    def test_returns_unhealthy_on_connect_error(self, respx_mock: respx.MockRouter):
        """Returns unhealthy when connection fails."""
        from gasclaw.health import _check_openclaw_gateway

        respx_mock.get("http://localhost:8080/health").mock(
            side_effect=httpx.ConnectError("refused")
        )
        result = _check_openclaw_gateway(8080)
        assert result == "unhealthy"

    def test_returns_unhealthy_on_timeout(self, respx_mock: respx.MockRouter):
        """Returns unhealthy when request times out."""
        from gasclaw.health import _check_openclaw_gateway

        respx_mock.get("http://localhost:8080/health").mock(
            side_effect=httpx.TimeoutException("timeout")
        )
        result = _check_openclaw_gateway(8080)
        assert result == "unhealthy"


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

    def test_check_service_oserror(self, monkeypatch):
        """Test _check_service returns 'unhealthy' on OSError (e.g., permission denied)."""
        from gasclaw.health import _check_service

        def _raise_oserror(*a, **kw):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", _raise_oserror)
        result = _check_service(["gt", "daemon", "status"], "daemon")
        assert result == "unhealthy"

    def test_git_error_returns_non_compliant(self, monkeypatch, tmp_path):
        """Git command failure returns non-compliant activity."""
        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 1, stderr=b"git error"),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None
        assert activity["error"] is not None

    def test_invalid_timestamp_returns_non_compliant(self, monkeypatch, tmp_path):
        """Invalid timestamp in git output returns non-compliant."""
        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"not-a-number\n"),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        assert activity["compliant"] is False

    def test_file_not_found_returns_non_compliant(self, monkeypatch, tmp_path):
        """FileNotFoundError (git not installed) returns non-compliant."""
        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        def raise_not_found(*a, **kw):
            raise FileNotFoundError("git not found")

        monkeypatch.setattr(subprocess, "run", raise_not_found)
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None

    def test_timeout_returns_non_compliant(self, monkeypatch, tmp_path):
        """TimeoutExpired returns non-compliant."""
        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0], timeout=10)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None

    def test_permission_error_returns_non_compliant(self, monkeypatch, tmp_path):
        """PermissionError returns non-compliant."""
        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        def raise_permission_error(*a, **kw):
            raise PermissionError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", raise_permission_error)
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        assert activity["compliant"] is False
        assert activity["last_commit_age"] is None
        assert activity["error"] is not None


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

    def test_list_agents_oserror(self, monkeypatch):
        """Test _list_agents returns empty list on OSError (e.g., permission denied)."""
        from gasclaw.health import _list_agents

        def _raise_oserror(*a, **kw):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", _raise_oserror)
        result = _list_agents()
        assert result == []

    def test_list_agents_nonzero_exit(self, monkeypatch):
        """Test _list_agents returns empty list when gt status returns non-zero."""
        from gasclaw.health import _list_agents

        def mock_run(*a, **kw):
            return subprocess.CompletedProcess(
                args=a[0] if a else ["cmd"], returncode=1, stderr=b"error"
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = _list_agents()
        assert result == []

    def test_list_agents_whitespace_only_lines_filtered(self, monkeypatch):
        """Test _list_agents filters out whitespace-only lines - Issue #66."""
        from gasclaw.health import _list_agents

        def mock_run(*a, **kw):
            # Return output with various whitespace-only lines
            return subprocess.CompletedProcess(
                args=a[0] if a else ["cmd"],
                returncode=0,
                stdout=b"mayor\n   \n  \t  \n\n\ndeacon\n \n witness\n",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = _list_agents()
        # Only the actual agent names should be included, not whitespace lines
        assert result == ["mayor", "deacon", "witness"]

    def test_list_agents_empty_lines_filtered(self, monkeypatch):
        """Test _list_agents filters out empty lines."""
        from gasclaw.health import _list_agents

        def mock_run(*a, **kw):
            return subprocess.CompletedProcess(
                args=a[0] if a else ["cmd"],
                returncode=0,
                stdout=b"agent1\n\nagent2\n\n\nagent3\n",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = _list_agents()
        assert result == ["agent1", "agent2", "agent3"]

    def test_list_agents_leading_trailing_whitespace_stripped(self, monkeypatch):
        """Test _list_agents strips leading/trailing whitespace from agent names."""
        from gasclaw.health import _list_agents

        def mock_run(*a, **kw):
            return subprocess.CompletedProcess(
                args=a[0] if a else ["cmd"],
                returncode=0,
                stdout=b"  mayor  \n\t deacon \t\n witness  \n",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = _list_agents()
        assert result == ["mayor", "deacon", "witness"]

    def test_list_agents_all_whitespace_returns_empty(self, monkeypatch):
        """Test _list_agents returns empty list when all lines are whitespace - Issue #66."""
        from gasclaw.health import _list_agents

        def mock_run(*a, **kw):
            return subprocess.CompletedProcess(
                args=a[0] if a else ["cmd"],
                returncode=0,
                stdout=b"   \n  \t  \n \n\n",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = _list_agents()
        assert result == []

    def test_list_agents_internal_whitespace_preserved(self, monkeypatch):
        """Test _list_agents preserves internal whitespace in agent names."""
        from gasclaw.health import _list_agents

        def mock_run(*a, **kw):
            return subprocess.CompletedProcess(
                args=a[0] if a else ["cmd"],
                returncode=0,
                stdout=b"crew worker 1\ncrew-worker-2\n",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = _list_agents()
        # Internal whitespace should be preserved
        assert result == ["crew worker 1", "crew-worker-2"]


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

    def test_summary_with_none_key_pool_values(self):
        """Summary shows ?/? instead of None/None for None values - Issue #65."""
        report = HealthReport(
            dolt="healthy",
            agents=["mayor"],
            key_pool={"total": None, "available": None},
        )
        summary = report.summary()
        # Should show ?/? not None/None
        assert "None" not in summary
        assert "?/?" in summary or "Keys: ?/" in summary

    def test_summary_with_partial_none_key_pool(self):
        """Summary handles partial None values in key_pool."""
        report = HealthReport(
            dolt="healthy",
            agents=["mayor"],
            key_pool={"total": 5, "available": None},
        )
        summary = report.summary()
        # Should show ?/5 (available is None -> ?, total is 5)
        assert "None" not in summary
        assert "?/5" in summary or "?/" in summary

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

    def test_summary_with_only_compliant_in_activity(self):
        """Summary handles activity with only 'compliant' key (no last_commit_age)."""
        report = HealthReport(
            dolt="healthy",
            agents=["mayor"],
            key_pool={"total": 1, "available": 1},
            activity={"compliant": True},  # No last_commit_age key
        )
        summary = report.summary()
        # Should show compliant status with ? for age
        assert "compliant" in summary.lower()

    def test_summary_activity_without_last_commit_age_key(self):
        """Summary handles activity dict missing last_commit_age key entirely."""
        report = HealthReport(
            dolt="healthy",
            agents=["mayor"],
            key_pool={"total": 1, "available": 1},
            activity={"compliant": False, "error": "some error"},  # No last_commit_age
        )
        summary = report.summary()
        assert "not compliant" in summary.lower()

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
    def test_check_health_with_timeout_expired(self, monkeypatch, respx_mock: respx.MockRouter):
        """check_health handles TimeoutExpired gracefully."""
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))

        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd=a[0], timeout=10)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        report = check_health(gateway_port=18789)
        # Should return report with unhealthy status, not raise
        assert report.dolt == "unhealthy"
        assert report.daemon == "unhealthy"

    def test_check_health_agents_with_file_not_found(
        self, monkeypatch, respx_mock: respx.MockRouter
    ):
        """_list_agents handles FileNotFoundError when gt not installed."""
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))

        def mock_run(cmd, **kw):
            if "status" in str(cmd) and "--agents" in str(cmd):
                raise FileNotFoundError("gt not found")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")

        monkeypatch.setattr(subprocess, "run", mock_run)
        report = check_health(gateway_port=18789)
        assert report.agents == []

    def test_check_health_agents_with_timeout(self, monkeypatch, respx_mock: respx.MockRouter):
        """_list_agents handles TimeoutExpired gracefully."""
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))

        def mock_run(cmd, **kw):
            if "status" in str(cmd) and "--agents" in str(cmd):
                raise subprocess.TimeoutExpired(cmd=["gt"], timeout=10)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"ok")

        monkeypatch.setattr(subprocess, "run", mock_run)
        report = check_health(gateway_port=18789)
        assert report.agents == []

    def test_check_agent_activity_zero_deadline(self, monkeypatch, tmp_path):
        """check_agent_activity with zero deadline requires recent commits."""
        import time

        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        # Use current timestamp so age is approximately 0
        now_ts = int(time.time())
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=f"{now_ts}\n".encode()),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=0)
        # Age should be 0 (or close to it), so 0 <= 0 is True
        assert activity["compliant"] is True
        assert activity["last_commit_age"] <= 1  # Should be very recent

    def test_check_agent_activity_very_large_deadline(self, monkeypatch, tmp_path):
        """check_agent_activity with very large deadline accepts old commits."""
        import time

        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        old_timestamp = int(time.time()) - 86400  # 1 day ago
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                a[0], 0, stdout=f"{old_timestamp}\n".encode()
            ),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=100000)
        assert activity["compliant"] is True


class TestCheckAgentActivityClockSkew:
    """Tests for future timestamp handling - Issue #67."""

    def test_future_timestamp_treated_as_now(self, monkeypatch, tmp_path):
        """Future timestamps are treated as age=0 (just now)."""
        import time

        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        # Future timestamp (1 hour from now)
        future_ts = int(time.time()) + 3600
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=f"{future_ts}\n".encode()),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        # Future timestamp should be treated as age=0 (compliant)
        assert activity["last_commit_age"] == 0
        assert activity["compliant"] is True
        assert activity["error"] is None

    def test_future_timestamp_logs_warning(self, monkeypatch, tmp_path, caplog):
        """Future timestamps log a warning about clock skew."""
        import logging
        import time

        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        # Future timestamp
        future_ts = int(time.time()) + 3600
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=f"{future_ts}\n".encode()),
        )

        with caplog.at_level(logging.WARNING):
            check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)

        assert "future" in caplog.text.lower()
        assert "clock skew" in caplog.text.lower()

    def test_very_future_timestamp_handled(self, monkeypatch, tmp_path):
        """Very future timestamps (days ahead) are handled correctly."""
        import time

        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        # Future timestamp (1 day from now)
        future_ts = int(time.time()) + 86400
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=f"{future_ts}\n".encode()),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        # Should still be treated as age=0
        assert activity["last_commit_age"] == 0
        assert activity["compliant"] is True

    def test_past_timestamp_unchanged(self, monkeypatch, tmp_path):
        """Past timestamps are handled normally."""
        import time

        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        # 30 minutes ago
        past_ts = int(time.time()) - 1800
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=f"{past_ts}\n".encode()),
        )
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=3600)
        # Should be ~1800 seconds ago, compliant
        assert 1790 <= activity["last_commit_age"] <= 1810
        assert activity["compliant"] is True

    def test_future_timestamp_with_zero_deadline(self, monkeypatch, tmp_path):
        """Future timestamp with zero deadline - should still be compliant."""
        import time

        git_dir = tmp_path / "git_repo"
        git_dir.mkdir()
        git_dot_git = git_dir / ".git"
        git_dot_git.mkdir()

        # Future timestamp
        future_ts = int(time.time()) + 3600
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=f"{future_ts}\n".encode()),
        )
        # Zero deadline would normally require age <= 0
        activity = check_agent_activity(project_dir=str(git_dir), deadline_seconds=0)
        # Age is set to 0, so 0 <= 0 is True
        assert activity["last_commit_age"] == 0
        assert activity["compliant"] is True

    def test_check_health_custom_gateway_port(self, monkeypatch, respx_mock: respx.MockRouter):
        """check_health uses custom gateway port for openclaw check."""
        respx_mock.get("http://localhost:99999/health").mock(return_value=httpx.Response(200))
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        report = check_health(gateway_port=99999)
        assert report.openclaw == "healthy"

    def test_openclaw_gateway_connection_error(self, monkeypatch, respx_mock: respx.MockRouter):
        """check_health returns unhealthy when openclaw gateway connection fails."""
        respx_mock.get("http://localhost:18789/health").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        report = check_health(gateway_port=18789)
        assert report.openclaw == "unhealthy"

    def test_openclaw_gateway_timeout(self, monkeypatch, respx_mock: respx.MockRouter):
        """check_health returns unhealthy when openclaw gateway times out."""
        respx_mock.get("http://localhost:18789/health").mock(
            side_effect=httpx.TimeoutException("Request timed out")
        )
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        report = check_health(gateway_port=18789)
        assert report.openclaw == "unhealthy"

    def test_openclaw_gateway_non_200_status(self, monkeypatch, respx_mock: respx.MockRouter):
        """check_health returns unhealthy when openclaw gateway returns non-200."""
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(503))
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: subprocess.CompletedProcess(a[0], 0, stdout=b"ok"),
        )
        report = check_health(gateway_port=18789)
        assert report.openclaw == "unhealthy"

    def test_check_health_with_oserror_on_service_check(
        self, monkeypatch, respx_mock: respx.MockRouter
    ):
        """check_health handles OSError on service checks - covers lines 55-58, 64-67."""
        respx_mock.get("http://localhost:18789/health").mock(return_value=httpx.Response(200))

        def raise_oserror(*a, **kw):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", raise_oserror)
        report = check_health(gateway_port=18789)
        # All services should be unhealthy due to OSError
        assert report.dolt == "unhealthy"
        assert report.daemon == "unhealthy"
        assert report.mayor == "unhealthy"
