"""Run openclaw doctor to verify system health and requirements."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class DoctorResult:
    """Result of running openclaw doctor."""

    healthy: bool
    returncode: int
    output: str

    def summary(self) -> str:
        """Human-readable summary."""
        status = "healthy" if self.healthy else "issues found"
        lines = [f"OpenClaw Doctor: {status}"]
        if not self.healthy and self.output:
            lines.append(self.output)
        return "\n".join(lines)


def run_doctor(*, repair: bool = False, timeout: int = 60) -> DoctorResult:
    """Run openclaw doctor and return the result.

    Args:
        repair: If True, run with --repair to auto-fix issues.
        timeout: Max seconds to wait for doctor to complete.

    Returns:
        DoctorResult with health status and output.

    """
    cmd = ["openclaw", "doctor", "--non-interactive"]
    if repair:
        cmd.append("--repair")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
        )
        output = result.stdout.decode(errors="replace")
        return DoctorResult(
            healthy=result.returncode == 0,
            returncode=result.returncode,
            output=output,
        )
    except FileNotFoundError:
        return DoctorResult(
            healthy=False,
            returncode=-1,
            output="openclaw not installed or not found in PATH",
        )
    except PermissionError:
        return DoctorResult(
            healthy=False,
            returncode=-1,
            output="openclaw binary exists but is not executable (permission denied)",
        )
    except OSError as e:
        return DoctorResult(
            healthy=False,
            returncode=-1,
            output=f"openclaw failed to execute: {e}",
        )
    except subprocess.TimeoutExpired:
        return DoctorResult(
            healthy=False,
            returncode=-1,
            output=f"openclaw doctor timed out after {timeout}s",
        )
