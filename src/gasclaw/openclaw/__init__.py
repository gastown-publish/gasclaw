"""OpenClaw integration module.

Provides installation, configuration, and lifecycle management
for the OpenClaw overseer service.
"""

from gasclaw.openclaw.auth import get_gateway_auth_token
from gasclaw.openclaw.doctor import DoctorResult, run_doctor
from gasclaw.openclaw.forum_manager import (
    ForumTopicError,
    ForumTopicManager,
    TopicConfig,
)
from gasclaw.openclaw.installer import write_openclaw_config
from gasclaw.openclaw.lifecycle import start_openclaw, stop_openclaw
from gasclaw.openclaw.skill_manager import install_skills

__all__ = [
    # Auth
    "get_gateway_auth_token",
    # Doctor
    "DoctorResult",
    "run_doctor",
    # Forum
    "ForumTopicError",
    "ForumTopicManager",
    "TopicConfig",
    # Installer
    "write_openclaw_config",
    # Lifecycle
    "start_openclaw",
    "stop_openclaw",
    # Skills
    "install_skills",
]
