"""Updater module for gasclaw dependencies.

Provides version checking, update application, and notification
for gt, claude, openclaw, and dolt components.
"""

from __future__ import annotations

from gasclaw.updater.applier import apply_updates
from gasclaw.updater.checker import check_versions
from gasclaw.updater.notifier import notify_telegram

__all__ = [
    "apply_updates",
    "check_versions",
    "notify_telegram",
]
