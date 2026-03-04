"""Gastown integration module.

Provides installation, configuration, and lifecycle management
for Gastown agents and services.
"""

from __future__ import annotations

from gasclaw.gastown.agent_config import configure_agent
from gasclaw.gastown.gt_feed import (
    ActivityEvent,
    GastownFeed,
    format_feed_for_telegram,
    get_recent_activity,
)
from gasclaw.gastown.installer import (
    gastown_install,
    setup_kimi_accounts,
)
from gasclaw.gastown.lifecycle import (
    start_daemon,
    start_dolt,
    start_mayor,
    stop_all,
)

__all__ = [
    "ActivityEvent",
    "GastownFeed",
    "configure_agent",
    "format_feed_for_telegram",
    "gastown_install",
    "get_recent_activity",
    "setup_kimi_accounts",
    "start_daemon",
    "start_dolt",
    "start_mayor",
    "stop_all",
]
