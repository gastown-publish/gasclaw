"""Health checks for all gasclaw subsystems.

OpenClaw acts as the overseer — this module provides the monitoring data
it needs to assess system health, agent activity, and compliance.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from gasclaw.openclaw.doctor import run_doctor


@dataclass
class HealthReport:
    """Complete health report for the gasclaw system."""

    dolt: str = "unknown"
    daemon: str = "unknown"
    mayor: str = "unknown"
    openclaw: str = "unknown"
    openclaw_doctor: str = "unknown"
    agents: list[str] = field(default_factory=list)
    key_pool: dict[str, Any] = field(default_factory=dict)
    activity: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Human-readable summary string."""
        avail = self.key_pool.get("available", "?")
        total = self.key_pool.get("total", "?")
        lines = [
            f"Dolt: {self.dolt}",
            f"Daemon: {self.daemon}",
            f"Mayor: {self.mayor}",
            f"OpenClaw: {self.openclaw}",
            f"OpenClaw Doctor: {self.openclaw_doctor}",
            f"Agents: {len(self.agents)} active ({', '.join(self.agents[:5])})",
            f"Keys: {avail}/{total} available",
        ]
        if self.activity:
            compliant = self.activity.get("compliant", False)
            age = self.activity.get("last_commit_age", "?")
            status = "compliant" if compliant else "NOT COMPLIANT"
            lines.append(f"Activity: {status} (last commit {age}s ago)")
        return "\n".join(lines)


def _check_service(cmd: list[str], service_name: str) -> str:
    """Run a health check command and return status."""
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return "healthy" if result.returncode == 0 else "unhealthy"
    except (OSError, subprocess.TimeoutExpired):
        return "unhealthy"


def _check_openclaw_gateway(gateway_port: int) -> str:
    """Check OpenClaw gateway health via HTTP request.

    Args:
        gateway_port: Port where the OpenClaw gateway is listening.

    Returns:
        "healthy" if the gateway responds with 200, "unhealthy" otherwise.
    """
    try:
        response = httpx.get(f"http://localhost:{gateway_port}/health", timeout=10)
        return "healthy" if response.status_code == 200 else "unhealthy"
    except (httpx.ConnectError, httpx.TimeoutException):
        return "unhealthy"


def _list_agents() -> list[str]:
    """Get list of running Gastown agents from gt status."""
    try:
        result = subprocess.run(
            ["gt", "status", "--agents"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.decode().splitlines() if line.strip()]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return []


def check_health(*, gateway_port: int = 18789) -> HealthReport:
    """Run all health checks and return a complete report.

    Args:
        gateway_port: OpenClaw gateway port for connectivity check.
    """
    doctor = run_doctor()
    return HealthReport(
        dolt=_check_service(["dolt", "sql", "--port", "3307", "-q", "SELECT 1"], "dolt"),
        daemon=_check_service(["gt", "daemon", "status"], "daemon"),
        mayor=_check_service(["gt", "mayor", "status"], "mayor"),
        openclaw=_check_openclaw_gateway(gateway_port),
        openclaw_doctor="healthy" if doctor.healthy else "unhealthy",
        agents=_list_agents(),
    )


def check_agent_activity(
    *,
    project_dir: str = "/project",
    deadline_seconds: int = 3600,
) -> dict[str, Any]:
    """Check if there has been recent git activity (push/PR/commit).

    The overseer (OpenClaw) uses this to enforce the activity benchmark:
    code must be pushed or a PR merged within the deadline window.

    Args:
        project_dir: Directory containing the git repository.
        deadline_seconds: Max allowed time since last activity.

    Returns:
        Dict with last_commit_age (seconds), compliant (bool), and error (str|None).
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            capture_output=True,
            timeout=10,
            cwd=project_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            last_ts = int(result.stdout.decode().strip())
            age = int(time.time() - last_ts)
            return {
                "last_commit_age": age,
                "compliant": age <= deadline_seconds,
                "error": None,
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass

    return {
        "last_commit_age": None,
        "compliant": False,
        "error": "failed to get git log",
    }

