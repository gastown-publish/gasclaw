"""OpenClaw integration module.

Provides installation, configuration, and lifecycle management
for the OpenClaw overseer service.
"""

from __future__ import annotations

from gasclaw.openclaw.auth import get_gateway_auth_token
from gasclaw.openclaw.doctor import DoctorResult, run_doctor
from gasclaw.openclaw.forum_manager import (
    ForumTopicError,
    ForumTopicManager,
    GroupForumState,
    TopicConfig,
)
from gasclaw.openclaw.installer import write_openclaw_config
from gasclaw.openclaw.lifecycle import start_openclaw, stop_openclaw
from gasclaw.openclaw.skill_manager import install_skills

__all__ = [
    "DoctorResult",
    "ForumTopicError",
    "ForumTopicManager",
    "GroupForumState",
    "TopicConfig",
    "get_gateway_auth_token",
    "install_skills",
    "run_doctor",
    "start_openclaw",
    "stop_openclaw",
    "write_openclaw_config",
]
