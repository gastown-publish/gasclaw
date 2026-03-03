"""OpenClaw integration module.

Provides installation, configuration, and lifecycle management
for the OpenClaw overseer service.
"""

from __future__ import annotations

from gasclaw.openclaw.auth import get_gateway_auth_token
from gasclaw.openclaw.doctor import DoctorResult, run_doctor
from gasclaw.openclaw.installer import write_openclaw_config
from gasclaw.openclaw.lifecycle import start_openclaw, stop_openclaw
from gasclaw.openclaw.skill_manager import install_skills

__all__ = [
    "get_gateway_auth_token",
    "DoctorResult",
    "run_doctor",
    "write_openclaw_config",
    "start_openclaw",
    "stop_openclaw",
    "install_skills",
]
