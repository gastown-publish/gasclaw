"""Tests for gasclaw.maintenance module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from gasclaw.maintenance import (
    checkout_and_test_pr,
    fix_on_branch,
    get_open_issues,
    get_open_prs,
    merge_pr,
    process_open_issues,
    process_open_prs,
    run_command,
    run_maintenance_cycle,
)


class TestRunCommand:
    def test_runs_command_successfully(self):
        result = run_command(["echo", "hello"], check=False)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_raises_on_failure_when_check_true(self):
        with pytest.raises(Exception):
            run_command(["false"], check=True)

    def test_returns_result_on_failure_when_check_false(self):
        result = run_command(["false"], check=False)
        assert result.returncode != 0

    def test_respects_timeout(self):
        with pytest.raises(Exception):
            run_command(["sleep", "10"], timeout=1)


class TestGetOpenPRs:
    @patch("gasclaw.maintenance.run_command")
    def test_returns_parsed_prs(self, mock_run):
        mock_prs = [
            {"number": 1, "title": "Fix bug", "headRefName": "fix/bug",
             "author": {"login": "user"}},
            {"number": 2, "title": "Add feature", "headRefName": "feat/thing",
             "author": {"login": "user"}},
        ]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_prs)
        mock_run.return_value = mock_result

        result = get_open_prs()

        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["title"] == "Add feature"

    @patch("gasclaw.maintenance.run_command")
    def test_returns_empty_list_on_error(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "API error"
        mock_run.return_value = mock_result

        result = get_open_prs()

        assert result == []

    @patch("gasclaw.maintenance.run_command")
    def test_returns_empty_list_on_exception(self, mock_run):
        mock_run.side_effect = Exception("Network error")

        result = get_open_prs()

        assert result == []


class TestGetOpenIssues:
    @patch("gasclaw.maintenance.run_command")
    def test_returns_parsed_issues(self, mock_run):
        mock_issues = [
            {"number": 10, "title": "Bug report"},
            {"number": 11, "title": "Feature request"},
        ]
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(mock_issues)
        mock_run.return_value = mock_result

        result = get_open_issues()

        assert len(result) == 2
        assert result[0]["number"] == 10

    @patch("gasclaw.maintenance.run_command")
    def test_returns_empty_list_on_error(self, mock_run):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = get_open_issues()

        assert result == []


class TestCheckoutAndTestPR:
    @patch("gasclaw.maintenance.run_command")
    def test_returns_true_when_tests_pass(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = checkout_and_test_pr(42, "fix/branch")

        assert result is True
        # Should checkout main, pull, checkout PR, and run tests
        calls = [call[0][0] for call in mock_run.call_args_list]
        assert ["git", "checkout", "main"] in calls
        assert ["git", "pull"] in calls
        assert ["gh", "pr", "checkout", "42", "--repo", "gastown-publish/gasclaw"] in calls

    @patch("gasclaw.maintenance.run_command")
    def test_returns_false_when_tests_fail(self, mock_run):
        # Make the pytest command fail
        def side_effect(cmd, **kwargs):
            if "pytest" in cmd:
                raise Exception("Tests failed")
            return MagicMock(returncode=0)

        mock_run.side_effect = side_effect

        result = checkout_and_test_pr(42, "fix/branch")

        assert result is False

    @patch("gasclaw.maintenance.run_command")
    def test_returns_false_on_exception(self, mock_run):
        mock_run.side_effect = Exception("Git error")

        result = checkout_and_test_pr(42, "fix/branch")

        assert result is False


class TestMergePR:
    @patch("gasclaw.maintenance.run_command")
    def test_returns_true_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)

        result = merge_pr(42)

        assert result is True
        calls = [call[0][0] for call in mock_run.call_args_list]
        assert [
            "gh", "pr", "merge", "42", "--repo", "gastown-publish/gasclaw",
            "--squash", "--delete-branch",
        ] in calls
        assert ["git", "checkout", "main"] in calls

    @patch("gasclaw.maintenance.run_command")
    def test_returns_false_on_failure(self, mock_run):
        mock_run.side_effect = Exception("Merge conflict")

        result = merge_pr(42)

        assert result is False


class TestFixOnBranch:
    @patch("gasclaw.maintenance.notify_telegram")
    def test_notifies_and_returns_false(self, mock_notify):
        result = fix_on_branch(42)

        assert result is False
        mock_notify.assert_called_once()
        assert "PR #42" in mock_notify.call_args[0][0]


class TestProcessOpenPRs:
    @patch("gasclaw.maintenance.merge_pr")
    @patch("gasclaw.maintenance.checkout_and_test_pr")
    @patch("gasclaw.maintenance.get_open_prs")
    def test_merges_passing_prs(self, mock_get_prs, mock_test, mock_merge):
        mock_get_prs.return_value = [
            {"number": 1, "title": "Fix", "headRefName": "fix/1"},
            {"number": 2, "title": "Feat", "headRefName": "feat/2"},
        ]
        mock_test.return_value = True
        mock_merge.return_value = True

        result = process_open_prs()

        assert result["total"] == 2
        assert result["merged"] == 2
        assert result["failed"] == 0
        assert mock_test.call_count == 2
        assert mock_merge.call_count == 2

    @patch("gasclaw.maintenance.merge_pr")
    @patch("gasclaw.maintenance.fix_on_branch")
    @patch("gasclaw.maintenance.checkout_and_test_pr")
    @patch("gasclaw.maintenance.get_open_prs")
    def test_handles_failing_prs(self, mock_get_prs, mock_test, mock_fix, mock_merge):
        mock_get_prs.return_value = [
            {"number": 1, "title": "Fix", "headRefName": "fix/1"},
        ]
        mock_test.return_value = False
        mock_fix.return_value = False

        result = process_open_prs()

        assert result["total"] == 1
        assert result["merged"] == 0
        assert result["failed"] == 1
        mock_merge.assert_not_called()

    @patch("gasclaw.maintenance.get_open_prs")
    def test_handles_no_prs(self, mock_get_prs):
        mock_get_prs.return_value = []

        result = process_open_prs()

        assert result["total"] == 0
        assert result["merged"] == 0


class TestProcessOpenIssues:
    @patch("gasclaw.maintenance.notify_telegram")
    @patch("gasclaw.maintenance.get_open_issues")
    def test_notifies_about_issues(self, mock_get_issues, mock_notify):
        mock_get_issues.return_value = [
            {"number": 10, "title": "Bug"},
            {"number": 11, "title": "Feature"},
        ]

        result = process_open_issues()

        assert result["total"] == 2
        assert mock_notify.call_count == 2

    @patch("gasclaw.maintenance.get_open_issues")
    def test_handles_no_issues(self, mock_get_issues):
        mock_get_issues.return_value = []

        result = process_open_issues()

        assert result["total"] == 0
        assert result["processed"] == 0


class TestRunMaintenanceCycle:
    @patch("gasclaw.maintenance.process_open_issues")
    @patch("gasclaw.maintenance.process_open_prs")
    def test_returns_combined_results(self, mock_prs, mock_issues):
        mock_prs.return_value = {"total": 2, "merged": 1, "failed": 0, "fixed": 0}
        mock_issues.return_value = {"total": 3, "processed": 0}

        result = run_maintenance_cycle()

        assert result["prs"]["total"] == 2
        assert result["prs"]["merged"] == 1
        assert result["issues"]["total"] == 3
