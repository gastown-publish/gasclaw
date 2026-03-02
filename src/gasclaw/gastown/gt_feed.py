"""Gastown activity feed for Telegram dashboard.

Integrates gt status/log output to provide activity updates to Telegram.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from typing import Any, cast

logger = logging.getLogger(__name__)

__all__ = [
    "ActivityEvent",
    "GastownFeed",
    "get_recent_activity",
    "format_feed_for_telegram",
]


@dataclass
class ActivityEvent:
    """Single activity event from Gastown."""

    type: str  # commit, pr, agent_start, agent_stop, etc.
    timestamp: str
    actor: str  # agent name or user
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "description": self.description,
            "metadata": self.metadata,
        }


class GastownFeed:
    """Reader for Gastown activity feed."""

    def __init__(self, project_dir: str = "/project") -> None:
        self.project_dir = project_dir

    def _run_gt_command(self, args: list[str]) -> str | None:
        """Run a gt command and return stdout."""
        try:
            result = subprocess.run(
                ["gt"] + args,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_dir,
            )
            if result.returncode == 0:
                return result.stdout
            logger.warning(f"gt command failed: {' '.join(args)} - {result.stderr}")
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to run gt command: {e}")
        return None

    def get_agent_status(self) -> list[dict[str, Any]]:
        """Get current agent status from gt status."""
        output = self._run_gt_command(["status", "--json"])
        if output:
            try:
                data = json.loads(output)
                return cast(list[dict[str, Any]], data.get("agents", []))
            except json.JSONDecodeError:
                logger.warning("Failed to parse gt status JSON")
        return []

    def get_recent_commits(self, limit: int = 5) -> list[ActivityEvent]:
        """Get recent commits from git log."""
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"-{limit}",
                    "--format=%H|%ai|%an|%s",
                    "--date=iso",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.project_dir,
            )
            if result.returncode == 0:
                events = []
                for line in result.stdout.strip().split("\n"):
                    if "|" in line:
                        parts = line.split("|", 3)
                        if len(parts) == 4:
                            hash_val, timestamp, author, message = parts
                            events.append(
                                ActivityEvent(
                                    type="commit",
                                    timestamp=timestamp,
                                    actor=author,
                                    description=message[:100],
                                    metadata={"hash": hash_val[:8]},
                                )
                            )
                return events
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to get git log: {e}")
        return []

    def get_recent_prs(self, limit: int = 5) -> list[ActivityEvent]:
        """Get recent PRs from gt pr list or git log with merge commits."""
        # Try to get merge commits as proxy for PR activity
        try:
            result = subprocess.run(
                [
                    "git",
                    "log",
                    f"-{limit * 2}",  # Get more to filter merges
                    "--format=%H|%ai|%an|%s",
                    "--merges",  # Only merge commits
                    "--date=iso",
                ],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=self.project_dir,
            )
            if result.returncode == 0 and result.stdout.strip():
                events = []
                for line in result.stdout.strip().split("\n")[:limit]:
                    if "|" in line:
                        parts = line.split("|", 3)
                        if len(parts) == 4:
                            hash_val, timestamp, author, message = parts
                            events.append(
                                ActivityEvent(
                                    type="pr_merge",
                                    timestamp=timestamp,
                                    actor=author,
                                    description=message[:100],
                                    metadata={"hash": hash_val[:8]},
                                )
                            )
                return events
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to get merge commits: {e}")
        return []

    def get_feed(self, limit: int = 10) -> list[ActivityEvent]:
        """Get combined feed of recent activity."""
        commits = self.get_recent_commits(limit // 2)
        prs = self.get_recent_prs(limit // 2)

        # Combine and sort by timestamp
        all_events = commits + prs
        all_events.sort(key=lambda e: e.timestamp, reverse=True)

        return all_events[:limit]

    def get_summary(self) -> dict[str, Any]:
        """Get activity summary for dashboard."""
        agents = self.get_agent_status()
        recent = self.get_feed(limit=5)

        # Count events by type
        commit_count = sum(1 for e in recent if e.type == "commit")
        pr_count = sum(1 for e in recent if e.type == "pr_merge")

        return {
            "active_agents": len(agents),
            "agent_names": [a.get("name", "unknown") for a in agents],
            "recent_commits": commit_count,
            "recent_prs": pr_count,
            "recent_activity": [e.to_dict() for e in recent],
            "status": "active" if agents else "idle",
        }


def get_recent_activity(
    project_dir: str = "/project",
    limit: int = 10,
) -> list[ActivityEvent]:
    """Convenience function to get recent activity.

    Args:
        project_dir: Project directory with git repository.
        limit: Maximum number of events to return.

    Returns:
        List of ActivityEvent objects.
    """
    feed = GastownFeed(project_dir)
    return feed.get_feed(limit)


def format_feed_for_telegram(
    summary: dict[str, Any],
    *,
    max_events: int = 5,
) -> str:
    """Format activity summary for Telegram message.

    Args:
        summary: Activity summary from GastownFeed.get_summary().
        max_events: Maximum number of events to include.

    Returns:
        Formatted markdown string for Telegram.
    """
    lines = [
        "📊 *Gastown Activity Dashboard*",
        "",
        f"🤖 *Active Agents:* {summary['active_agents']}",
    ]

    if summary.get("agent_names"):
        agent_list = ", ".join(summary["agent_names"][:5])
        lines.append(f"   {agent_list}")

    lines.append("")
    lines.append(f"📝 *Recent Commits:* {summary['recent_commits']}")
    lines.append(f"🔀 *Recent PRs:* {summary['recent_prs']}")
    lines.append("")

    # Recent activity
    events = summary.get("recent_activity", [])[:max_events]
    if events:
        lines.append("🕐 *Recent Activity:*")
        for event in events:
            emoji = "📝" if event["type"] == "commit" else "🔀"
            desc = event["description"][:50]
            if len(event["description"]) > 50:
                desc += "..."
            actor = event["actor"][:15]
            lines.append(f"  {emoji} {desc} — _{actor}_")
    else:
        lines.append("🕐 *Recent Activity:* None")

    lines.append("")
    status_emoji = "🟢" if summary["status"] == "active" else "🟡"
    lines.append(f"{status_emoji} *Status:* {summary['status'].upper()}")

    return "\n".join(lines)
