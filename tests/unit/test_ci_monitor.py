"""Tests for CI failure monitoring (issue #248)."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

from gasclaw.ci_monitor import (
    CIFailure,
    check_ci_failures,
    create_failure_issue,
    format_failure_message,
    get_failed_workflows,
    is_duplicate_issue,
    load_seen_failures,
    save_seen_failures,
)


class TestGetFailedWorkflows:
    """Tests for getting failed workflows from gh CLI."""

    def test_get_failed_workflows_success(self):
        """Successfully parse failed workflows from gh CLI output."""
        mock_output = """
        [
          {
            "databaseId": 12345,
            "name": "Test Workflow",
            "status": "completed",
            "conclusion": "failure",
            "url": "https://github.com/gastown-publish/gasclaw/actions/runs/12345",
            "startedAt": "2026-03-03T10:00:00Z"
          },
          {
            "databaseId": 12346,
            "name": "Build Workflow",
            "status": "completed",
            "conclusion": "failure",
            "url": "https://github.com/gastown-publish/gasclaw/actions/runs/12346",
            "startedAt": "2026-03-03T11:00:00Z"
          }
        ]
        """

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=mock_output,
                stderr=""
            )
            failures = get_failed_workflows("gastown-publish/gasclaw")

        assert len(failures) == 2
        assert failures[0].run_id == "12345"
        assert failures[0].workflow_name == "Test Workflow"
        assert failures[0].url == "https://github.com/gastown-publish/gasclaw/actions/runs/12345"

    def test_get_failed_workflows_empty(self):
        """Handle empty list of failures."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            failures = get_failed_workflows("gastown-publish/gasclaw")

        assert failures == []

    def test_get_failed_workflows_command_failure(self):
        """Handle gh CLI command failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="error"
            )
            failures = get_failed_workflows("gastown-publish/gasclaw")

        assert failures == []

    def test_get_failed_workflows_invalid_json(self):
        """Handle invalid JSON output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="invalid json",
                stderr=""
            )
            failures = get_failed_workflows("gastown-publish/gasclaw")

        assert failures == []

    def test_get_failed_workflows_exception(self):
        """Handle subprocess exception."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")
            failures = get_failed_workflows("gastown-publish/gasclaw")

        assert failures == []


class TestIsDuplicateIssue:
    """Tests for duplicate issue detection."""

    def test_is_duplicate_true(self):
        """Returns True if run_id already seen."""
        seen = {"12345", "12346"}
        assert is_duplicate_issue("12345", seen) is True

    def test_is_duplicate_false(self):
        """Returns False if run_id not seen."""
        seen = {"12345", "12346"}
        assert is_duplicate_issue("99999", seen) is False

    def test_is_duplicate_empty(self):
        """Returns False for empty seen set."""
        assert is_duplicate_issue("12345", set()) is False


class TestCreateFailureIssue:
    """Tests for creating GitHub issues."""

    def test_create_issue_success(self):
        """Successfully create an issue."""
        failure = CIFailure(
            run_id="12345",
            workflow_name="Test Workflow",
            url="https://github.com/org/repo/actions/runs/12345",
            started_at="2026-03-03T10:00:00Z"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = create_failure_issue("gastown-publish/gasclaw", failure)

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "gh" in call_args
        assert "issue" in call_args
        assert "create" in call_args
        assert "ci-failure" in call_args

    def test_create_issue_failure(self):
        """Handle issue creation failure."""
        failure = CIFailure(
            run_id="12345",
            workflow_name="Test Workflow",
            url="https://github.com/org/repo/actions/runs/12345",
            started_at="2026-03-03T10:00:00Z"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            result = create_failure_issue("gastown-publish/gasclaw", failure)

        assert result is False

    def test_create_issue_exception(self):
        """Handle exception during issue creation."""
        failure = CIFailure(
            run_id="12345",
            workflow_name="Test Workflow",
            url="https://github.com/org/repo/actions/runs/12345",
            started_at="2026-03-03T10:00:00Z"
        )

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("command failed")
            result = create_failure_issue("gastown-publish/gasclaw", failure)

        assert result is False


class TestFormatFailureMessage:
    """Tests for formatting failure notifications."""

    def test_format_failure_message(self):
        """Format a failure for Telegram notification."""
        failure = CIFailure(
            run_id="12345",
            workflow_name="Test Workflow",
            url="https://github.com/org/repo/actions/runs/12345",
            started_at="2026-03-03T10:00:00Z"
        )

        message = format_failure_message(failure)

        assert "Test Workflow" in message
        assert "12345" in message
        assert "https://github.com/org/repo/actions/runs/12345" in message
        assert "CI Failure" in message


class TestSeenFailuresPersistence:
    """Tests for loading/saving seen failure IDs."""

    def test_load_seen_failures_file_exists(self, tmp_path):
        """Load seen failures from existing file."""
        state_file = tmp_path / "ci_failures.json"
        state_file.write_text(json.dumps({"seen": ["12345", "12346"]}))

        seen = load_seen_failures(str(state_file))

        assert seen == {"12345", "12346"}

    def test_load_seen_failures_missing_file(self, tmp_path):
        """Return empty set for missing file."""
        seen = load_seen_failures(str(tmp_path / "nonexistent.json"))
        assert seen == set()

    def test_load_seen_failures_invalid_json(self, tmp_path):
        """Return empty set for invalid JSON."""
        state_file = tmp_path / "ci_failures.json"
        state_file.write_text("invalid json")

        seen = load_seen_failures(str(state_file))
        assert seen == set()

    def test_save_seen_failures(self, tmp_path):
        """Save seen failures to file."""
        state_file = tmp_path / "ci_failures.json"

        save_seen_failures({"12345", "12346"}, str(state_file))

        data = json.loads(state_file.read_text())
        assert set(data["seen"]) == {"12345", "12346"}

    def test_save_seen_failures_creates_dir(self, tmp_path):
        """Create directory if needed when saving."""
        state_file = tmp_path / "subdir" / "ci_failures.json"

        save_seen_failures({"12345"}, str(state_file))

        assert state_file.exists()


class TestCheckCIFailures:
    """Integration tests for the main check function."""

    def test_check_ci_failures_creates_issues(self):
        """Create issues for new failures."""
        failures = [
            CIFailure(
                run_id="12345",
                workflow_name="Test Workflow",
                url="https://github.com/org/repo/actions/runs/12345",
                started_at="2026-03-03T10:00:00Z"
            )
        ]

        with (
            patch("gasclaw.ci_monitor.get_failed_workflows", return_value=failures),
            patch("gasclaw.ci_monitor.load_seen_failures", return_value=set()),
            patch("gasclaw.ci_monitor.save_seen_failures") as mock_save,
            patch("gasclaw.ci_monitor.create_failure_issue", return_value=True),
        ):
            result = check_ci_failures("gastown-publish/gasclaw")

        assert result["checked"] == 1
        assert result["new"] == 1
        assert result["duplicates"] == 0
        mock_save.assert_called_once()

    def test_check_ci_failures_skips_duplicates(self):
        """Skip duplicate failures but keep them in history."""
        failures = [
            CIFailure(
                run_id="12345",
                workflow_name="Test Workflow",
                url="https://github.com/org/repo/actions/runs/12345",
                started_at="2026-03-03T10:00:00Z"
            )
        ]

        with (
            patch("gasclaw.ci_monitor.get_failed_workflows", return_value=failures),
            patch("gasclaw.ci_monitor.load_seen_failures", return_value={"12345"}),
            patch("gasclaw.ci_monitor.save_seen_failures") as mock_save,
            patch("gasclaw.ci_monitor.create_failure_issue") as mock_create,
        ):
            result = check_ci_failures("gastown-publish/gasclaw")

        assert result["checked"] == 1
        assert result["new"] == 0
        assert result["duplicates"] == 1
        mock_create.assert_not_called()
        # History is saved even for duplicates (to keep them in history)
        mock_save.assert_called_once()

    def test_check_ci_failures_no_failures(self):
        """Handle no failures case."""
        with (
            patch("gasclaw.ci_monitor.get_failed_workflows", return_value=[]),
            patch("gasclaw.ci_monitor.load_seen_failures", return_value=set()),
        ):
            result = check_ci_failures("gastown-publish/gasclaw")

        assert result["checked"] == 0
        assert result["new"] == 0
        assert result["duplicates"] == 0

    def test_check_ci_failures_limits_history(self):
        """Limit seen failures history to prevent unbounded growth."""
        # Create many old failures plus one new one
        old_ids = [str(i) for i in range(150)]
        failures = [
            CIFailure(
                run_id="99999",  # New failure not in history
                workflow_name="Test Workflow",
                url="https://github.com/org/repo/actions/runs/99999",
                started_at="2026-03-03T10:00:00Z"
            )
        ]

        with (
            patch("gasclaw.ci_monitor.get_failed_workflows", return_value=failures),
            patch("gasclaw.ci_monitor.load_seen_failures", return_value=set(old_ids)),
            patch("gasclaw.ci_monitor.save_seen_failures") as mock_save,
            patch("gasclaw.ci_monitor.create_failure_issue", return_value=True),
        ):
            check_ci_failures("gastown-publish/gasclaw")

        # Check that save was called with limited set
        assert mock_save.called
        saved = mock_save.call_args[0][0]
        assert len(saved) == 100  # Max history size


class TestCIFailureDataclass:
    """Tests for CIFailure dataclass methods."""

    def test_unique_id(self):
        """Test unique_id method generates correct identifier."""
        failure = CIFailure(
            run_id="12345",
            workflow_name="Test Workflow",
            url="https://github.com/org/repo/actions/runs/12345",
            started_at="2026-03-03T10:00:00Z"
        )
        assert failure.unique_id() == "Test Workflow:12345"

    def test_unique_id_with_special_chars(self):
        """Test unique_id with special characters in workflow name."""
        failure = CIFailure(
            run_id="99999",
            workflow_name="Build / Test & Deploy",
            url="https://github.com/org/repo/actions/runs/99999",
            started_at="2026-03-03T10:00:00Z"
        )
        assert failure.unique_id() == "Build / Test & Deploy:99999"


class TestSaveSeenFailuresErrors:
    """Tests for save_seen_failures error handling."""

    def test_save_seen_failures_ioerror(self, tmp_path, caplog):
        """Test IOError handling when saving fails."""
        from unittest.mock import patch

        state_file = tmp_path / "ci_failures.json"

        # Mock open to raise IOError
        with (
            patch("builtins.open", side_effect=OSError("Permission denied")),
            caplog.at_level(logging.WARNING),
        ):
            save_seen_failures({"12345"}, str(state_file))

        assert "Failed to save seen failures" in caplog.text
        assert "Permission denied" in caplog.text


class TestCheckCIFailuresNotification:
    """Tests for notification handling in check_ci_failures."""

    def test_notification_success(self):
        """Test successful notification callback."""
        failures = [
            CIFailure(
                run_id="12345",
                workflow_name="Test Workflow",
                url="https://github.com/org/repo/actions/runs/12345",
                started_at="2026-03-03T10:00:00Z"
            )
        ]

        notifications = []

        def mock_send_notification(msg):
            notifications.append(msg)

        with (
            patch("gasclaw.ci_monitor.get_failed_workflows", return_value=failures),
            patch("gasclaw.ci_monitor.load_seen_failures", return_value=set()),
            patch("gasclaw.ci_monitor.save_seen_failures"),
            patch("gasclaw.ci_monitor.create_failure_issue", return_value=True),
        ):
            result = check_ci_failures(
                "gastown-publish/gasclaw",
                send_notification=mock_send_notification
            )

        assert result["new"] == 1
        assert len(notifications) == 1
        assert "Test Workflow" in notifications[0]

    def test_notification_failure(self, caplog):
        """Test notification callback exception handling."""
        failures = [
            CIFailure(
                run_id="12345",
                workflow_name="Test Workflow",
                url="https://github.com/org/repo/actions/runs/12345",
                started_at="2026-03-03T10:00:00Z"
            )
        ]

        def failing_notification(msg):
            raise Exception("Notification service down")

        with (
            patch("gasclaw.ci_monitor.get_failed_workflows", return_value=failures),
            patch("gasclaw.ci_monitor.load_seen_failures", return_value=set()),
            patch("gasclaw.ci_monitor.save_seen_failures"),
            patch("gasclaw.ci_monitor.create_failure_issue", return_value=True),
            caplog.at_level(logging.WARNING),
        ):
            result = check_ci_failures(
                "gastown-publish/gasclaw",
                send_notification=failing_notification
            )

        assert result["new"] == 1
        assert "Failed to send notification" in caplog.text
        assert "Notification service down" in caplog.text

    def test_no_notification_callback(self):
        """Test that None callback doesn't cause issues."""
        failures = [
            CIFailure(
                run_id="12345",
                workflow_name="Test Workflow",
                url="https://github.com/org/repo/actions/runs/12345",
                started_at="2026-03-03T10:00:00Z"
            )
        ]

        with (
            patch("gasclaw.ci_monitor.get_failed_workflows", return_value=failures),
            patch("gasclaw.ci_monitor.load_seen_failures", return_value=set()),
            patch("gasclaw.ci_monitor.save_seen_failures"),
            patch("gasclaw.ci_monitor.create_failure_issue", return_value=True),
        ):
            result = check_ci_failures(
                "gastown-publish/gasclaw",
                            send_notification=None
                        )

        assert result["new"] == 1
        # No notification sent, but no error either
