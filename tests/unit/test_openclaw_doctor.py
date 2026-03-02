"""Tests for gasclaw.openclaw.doctor."""

from __future__ import annotations

import subprocess

from gasclaw.openclaw.doctor import DoctorResult, run_doctor


class TestRunDoctor:
    def test_returns_healthy_on_success(self, monkeypatch):
        monkeypatch.setattr(
            "gasclaw.openclaw.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=a[0], returncode=0, stdout=b"All checks passed\n", stderr=b""
            ),
        )
        result = run_doctor()
        assert result.healthy is True
        assert result.returncode == 0

    def test_returns_unhealthy_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            "gasclaw.openclaw.doctor.subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=a[0], returncode=1,
                stdout=b"Config issues found\nMissing gateway auth\n",
                stderr=b"",
            ),
        )
        result = run_doctor()
        assert result.healthy is False
        assert result.returncode == 1
        assert "Config issues" in result.output

    def test_runs_non_interactive_by_default(self, monkeypatch):
        captured_args = {}

        def mock_run(cmd, **kwargs):
            captured_args["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"OK", stderr=b"")

        monkeypatch.setattr("gasclaw.openclaw.doctor.subprocess.run", mock_run)
        run_doctor()
        assert "--non-interactive" in captured_args["cmd"]

    def test_repair_mode(self, monkeypatch):
        captured_args = {}

        def mock_run(cmd, **kwargs):
            captured_args["cmd"] = cmd
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout=b"Repaired", stderr=b""
            )

        monkeypatch.setattr("gasclaw.openclaw.doctor.subprocess.run", mock_run)
        run_doctor(repair=True)
        assert "--repair" in captured_args["cmd"]

    def test_handles_missing_binary(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            raise FileNotFoundError("openclaw not found")

        monkeypatch.setattr("gasclaw.openclaw.doctor.subprocess.run", mock_run)
        result = run_doctor()
        assert result.healthy is False
        assert "not found" in result.output.lower() or "not installed" in result.output.lower()

    def test_handles_timeout(self, monkeypatch):
        def mock_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=60)

        monkeypatch.setattr("gasclaw.openclaw.doctor.subprocess.run", mock_run)
        result = run_doctor()
        assert result.healthy is False
        assert "timed out" in result.output.lower()


class TestDoctorResult:
    def test_summary_healthy(self):
        result = DoctorResult(healthy=True, returncode=0, output="All checks passed")
        assert "healthy" in result.summary().lower()

    def test_summary_unhealthy(self):
        result = DoctorResult(healthy=False, returncode=1, output="Gateway auth missing")
        summary = result.summary()
        assert "unhealthy" in summary.lower() or "issue" in summary.lower()
        assert "Gateway auth missing" in summary
