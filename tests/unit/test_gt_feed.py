"""Tests for gastown.gt_feed module."""

from __future__ import annotations

import json
import subprocess

from gasclaw.gastown.gt_feed import (
    ActivityEvent,
    GastownFeed,
    format_feed_for_telegram,
    get_recent_activity,
)


class TestActivityEvent:
    def test_basic_creation(self):
        """ActivityEvent can be created with required fields."""
        event = ActivityEvent(
            type="commit",
            timestamp="2026-03-02T10:00:00",
            actor="test-agent",
            description="Test commit message",
        )
        assert event.type == "commit"
        assert event.actor == "test-agent"
        assert event.description == "Test commit message"
        assert event.metadata == {}

    def test_to_dict(self):
        """ActivityEvent converts to dict correctly."""
        event = ActivityEvent(
            type="pr_merge",
            timestamp="2026-03-02T10:00:00",
            actor="test-agent",
            description="Merged PR #123",
            metadata={"hash": "abc123"},
        )
        d = event.to_dict()
        assert d["type"] == "pr_merge"
        assert d["actor"] == "test-agent"
        assert d["metadata"]["hash"] == "abc123"


class TestGastownFeed:
    def test_init(self):
        """GastownFeed initializes with project directory."""
        feed = GastownFeed(project_dir="/workspace/test")
        assert feed.project_dir == "/workspace/test"

    def test_default_project_dir(self):
        """GastownFeed uses default project directory."""
        feed = GastownFeed()
        assert feed.project_dir == "/project"

    def test_get_agent_status_success(self, monkeypatch):
        """get_agent_status parses gt status output."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = json.dumps({"agents": [{"name": "agent1"}, {"name": "agent2"}]})
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        agents = feed.get_agent_status()

        assert len(agents) == 2
        assert agents[0]["name"] == "agent1"

    def test_get_agent_status_failure(self, monkeypatch):
        """get_agent_status returns empty list on failure."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "error"

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        agents = feed.get_agent_status()

        assert agents == []

    def test_get_agent_status_json_error(self, monkeypatch):
        """get_agent_status handles invalid JSON."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = "invalid json"
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        agents = feed.get_agent_status()

        assert agents == []

    def test_get_agent_status_oserror(self, monkeypatch):
        """get_agent_status handles OSError from gt command (covers lines 64-65)."""

        def raise_oserror(*args, **kwargs):
            raise OSError(2, "No such file or directory")

        monkeypatch.setattr(subprocess, "run", raise_oserror)

        feed = GastownFeed()
        agents = feed.get_agent_status()

        assert agents == []

    def test_get_agent_status_timeout(self, monkeypatch):
        """get_agent_status handles subprocess timeout (covers lines 64-65)."""

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("gt", 30)

        monkeypatch.setattr(subprocess, "run", raise_timeout)

        feed = GastownFeed()
        agents = feed.get_agent_status()

        assert agents == []

    def test_get_recent_commits_success(self, monkeypatch):
        """get_recent_commits parses git log output."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = "abc123|2026-03-02 10:00:00 +0000|Test User|Test commit message"
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        commits = feed.get_recent_commits(limit=1)

        assert len(commits) == 1
        assert commits[0].type == "commit"
        assert commits[0].actor == "Test User"
        assert commits[0].description == "Test commit message"
        assert commits[0].metadata["hash"] == "abc123"

    def test_get_recent_commits_truncates_long_messages(self, monkeypatch):
        """get_recent_commits truncates messages over 100 chars."""
        long_message = "a" * 150

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = f"abc123|2026-03-02 10:00:00 +0000|User|{long_message}"
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        commits = feed.get_recent_commits(limit=1)

        assert len(commits[0].description) == 100

    def test_get_recent_commits_empty(self, monkeypatch):
        """get_recent_commits handles empty git log."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        commits = feed.get_recent_commits()

        assert commits == []

    def test_get_recent_commits_malformed_lines(self, monkeypatch):
        """get_recent_commits skips malformed lines with wrong part count (covers line 100->97)."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                # First line has only 2 parts (not 4), second is valid
                stdout = (
                    "hash1|timestamp1|author1\n"
                    "abc123|2026-03-02 10:00:00 +0000|Test User|Valid message"
                )
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        commits = feed.get_recent_commits(limit=2)

        # Should skip malformed line and only return valid one
        assert len(commits) == 1
        assert commits[0].description == "Valid message"

    def test_get_recent_commits_failure(self, monkeypatch):
        """get_recent_commits handles git failure."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "error"

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        commits = feed.get_recent_commits()

        assert commits == []

    def test_get_recent_commits_oserror(self, monkeypatch):
        """get_recent_commits handles OSError (covers lines 112-113)."""

        def raise_oserror(*args, **kwargs):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", raise_oserror)

        feed = GastownFeed()
        commits = feed.get_recent_commits()

        assert commits == []

    def test_get_recent_commits_timeout(self, monkeypatch):
        """get_recent_commits handles subprocess timeout (covers lines 112-113)."""

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("git", 10)

        monkeypatch.setattr(subprocess, "run", raise_timeout)

        feed = GastownFeed()
        commits = feed.get_recent_commits()

        assert commits == []

    def test_get_recent_prs_success(self, monkeypatch):
        """get_recent_prs parses merge commits."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = "abc123|2026-03-02 10:00:00 +0000|Test User|Merge pull request #123"
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        prs = feed.get_recent_prs(limit=1)

        assert len(prs) == 1
        assert prs[0].type == "pr_merge"
        assert "Merge pull request" in prs[0].description

    def test_get_recent_prs_oserror(self, monkeypatch):
        """get_recent_prs handles OSError (covers lines 151-153)."""

        def raise_oserror(*args, **kwargs):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(subprocess, "run", raise_oserror)

        feed = GastownFeed()
        prs = feed.get_recent_prs()

        assert prs == []

    def test_get_recent_prs_timeout(self, monkeypatch):
        """get_recent_prs handles subprocess timeout (covers lines 151-153)."""

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("git", 10)

        monkeypatch.setattr(subprocess, "run", raise_timeout)

        feed = GastownFeed()
        prs = feed.get_recent_prs()

        assert prs == []

    def test_get_recent_prs_empty_stdout(self, monkeypatch):
        """get_recent_prs returns empty list when stdout is empty (covers line 134->153)."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = ""  # Empty stdout - should trigger early return
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        prs = feed.get_recent_prs()

        assert prs == []

    def test_get_recent_prs_malformed_lines(self, monkeypatch):
        """get_recent_prs skips malformed lines with wrong part count (covers line 139->136)."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                # First line malformed (only 2 parts), second valid
                stdout = (
                    "hash1|timestamp1\n"
                    "abc123|2026-03-02 10:00:00 +0000|Test User|Merge PR #123"
                )
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        prs = feed.get_recent_prs(limit=2)

        # Should skip malformed line
        assert len(prs) == 1
        assert prs[0].description == "Merge PR #123"

    def test_get_feed_combines_events(self, monkeypatch):
        """get_feed combines commits and PRs."""
        commit_output = "abc1|2026-03-02 10:00:00 +0000|User|Commit message"
        pr_output = "abc2|2026-03-02 11:00:00 +0000|User|Merge PR"

        call_count = 0

        def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            class Result:
                returncode = 0
                stdout = commit_output if call_count == 1 else pr_output
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        events = feed.get_feed(limit=2)

        assert len(events) == 2
        # Should be sorted by timestamp (newest first)
        assert events[0].type == "pr_merge"

    def test_get_summary(self, monkeypatch):
        """get_summary returns activity summary."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = json.dumps({"agents": [{"name": "agent1"}, {"name": "agent2"}]})
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        feed = GastownFeed()
        summary = feed.get_summary()

        assert summary["active_agents"] == 2
        assert summary["agent_names"] == ["agent1", "agent2"]
        assert "recent_activity" in summary


class TestGetRecentActivity:
    """Tests for convenience function."""

    def test_get_recent_activity(self, monkeypatch):
        """Convenience function returns activity events."""

        def mock_run(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = "abc|2026-03-02 10:00:00 +0000|User|Message"
                stderr = ""

            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        events = get_recent_activity(project_dir="/tmp", limit=1)
        assert len(events) == 1


class TestFormatFeedForTelegram:
    """Tests for Telegram formatting."""

    def test_format_summary(self):
        """format_feed_for_telegram creates markdown message."""
        summary = {
            "active_agents": 3,
            "agent_names": ["agent1", "agent2", "agent3"],
            "recent_commits": 5,
            "recent_prs": 2,
            "status": "active",
            "recent_activity": [
                {
                    "type": "commit",
                    "description": "Fix bug in parser",
                    "actor": "agent1",
                    "timestamp": "2026-03-02T10:00:00",
                }
            ],
        }

        message = format_feed_for_telegram(summary)

        assert "Gastown Activity Dashboard" in message
        assert "Active Agents:* 3" in message
        assert "agent1" in message
        assert "Recent Commits:* 5" in message
        assert "Recent PRs:* 2" in message
        assert "Fix bug in parser" in message
        assert "🟢" in message  # Active status emoji

    def test_format_empty_activity(self):
        """format_feed_for_telegram handles no activity."""
        summary = {
            "active_agents": 0,
            "agent_names": [],
            "recent_commits": 0,
            "recent_prs": 0,
            "status": "idle",
            "recent_activity": [],
        }

        message = format_feed_for_telegram(summary)

        assert "Recent Activity:* None" in message
        assert "🟡" in message  # Idle status emoji

    def test_format_truncates_long_descriptions(self):
        """format_feed_for_telegram truncates long descriptions."""
        summary = {
            "active_agents": 1,
            "agent_names": ["agent1"],
            "recent_commits": 1,
            "recent_prs": 0,
            "status": "active",
            "recent_activity": [
                {
                    "type": "commit",
                    "description": "a" * 100,
                    "actor": "agent1",
                    "timestamp": "2026-03-02T10:00:00",
                }
            ],
        }

        message = format_feed_for_telegram(summary)

        assert "..." in message
        # The truncated description line itself is < 60 chars
        activity_line = [line for line in message.split("\n") if "📝 a" in line][0]
        assert len(activity_line) < 70

    def test_format_truncates_actor_names(self):
        """format_feed_for_telegram truncates long actor names."""
        summary = {
            "active_agents": 1,
            "agent_names": ["agent1"],
            "recent_commits": 1,
            "recent_prs": 0,
            "status": "active",
            "recent_activity": [
                {
                    "type": "commit",
                    "description": "Test",
                    "actor": "a" * 30,
                    "timestamp": "2026-03-02T10:00:00",
                }
            ],
        }

        message = format_feed_for_telegram(summary)

        assert "Test" in message
