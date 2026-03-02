"""Automated maintenance loop for gasclaw repository.

This module provides continuous maintenance capabilities:
- Check and merge open PRs
- Fix open issues
- Improve test coverage
- Maintain code quality

Can be run as a standalone script or imported as a module.
"""

from __future__ import annotations

import subprocess
import time

from gasclaw.logging_config import get_logger, setup_logging
from gasclaw.updater.notifier import notify_telegram

setup_logging()
logger = get_logger(__name__)

# Repository configuration
REPO = "gastown-publish/gasclaw"


def run_command(
    cmd: list[str], *, check: bool = True, timeout: int = 120
) -> subprocess.CompletedProcess:
    """Run a shell command and return the result.

    Args:
        cmd: Command and arguments as a list.
        check: If True, raise CalledProcessError on non-zero exit.
        timeout: Max seconds to wait for command.

    Returns:
        CompletedProcess with returncode, stdout, stderr.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result


def get_open_prs() -> list[dict]:
    """Get list of open PRs from GitHub.

    Returns:
        List of PR dicts with number, title, branch, and author.
    """
    try:
        result = run_command(
            [
                "gh", "pr", "list", "--repo", REPO, "--state", "open",
                "--json", "number,title,headRefName,author",
            ],
            check=False,
        )
        if result.returncode != 0:
            logger.warning("Failed to list PRs: %s", result.stderr)
            return []

        import json
        return json.loads(result.stdout)
    except Exception as e:
        logger.error("Error getting open PRs: %s", e)
        return []


def get_open_issues() -> list[dict]:
    """Get list of open issues from GitHub.

    Returns:
        List of issue dicts with number and title.
    """
    try:
        result = run_command(
            ["gh", "issue", "list", "--repo", REPO, "--state", "open", "--json", "number,title"],
            check=False,
        )
        if result.returncode != 0:
            logger.warning("Failed to list issues: %s", result.stderr)
            return []

        import json
        return json.loads(result.stdout)
    except Exception as e:
        logger.error("Error getting open issues: %s", e)
        return []


def checkout_and_test_pr(pr_number: int, branch: str) -> bool:
    """Checkout a PR branch and run tests.

    Args:
        pr_number: The PR number.
        branch: The branch name to checkout.

    Returns:
        True if tests pass, False otherwise.
    """
    logger.info("Checking out PR #%d: %s", pr_number, branch)
    try:
        # Ensure we're on main and have latest
        run_command(["git", "checkout", "main"])
        run_command(["git", "pull"])

        # Checkout the PR
        run_command(["gh", "pr", "checkout", str(pr_number), "--repo", REPO])

        # Run tests
        logger.info("Running tests for PR #%d", pr_number)
        result = run_command(
            ["python", "-m", "pytest", "tests/unit", "-v"], check=False, timeout=180
        )

        if result.returncode == 0:
            logger.info("Tests passed for PR #%d", pr_number)
            return True
        else:
            stdout_snippet = result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            logger.warning("Tests failed for PR #%d: %s", pr_number, stdout_snippet)
            return False

    except Exception as e:
        logger.error("Error testing PR #%d: %s", pr_number, e)
        return False


def merge_pr(pr_number: int) -> bool:
    """Merge a PR using squash merge.

    Args:
        pr_number: The PR number to merge.

    Returns:
        True if merge succeeded, False otherwise.
    """
    logger.info("Merging PR #%d", pr_number)
    try:
        run_command(
            ["gh", "pr", "merge", str(pr_number), "--repo", REPO, "--squash", "--delete-branch"]
        )

        # Return to main and pull
        run_command(["git", "checkout", "main"])
        run_command(["git", "pull"])

        logger.info("Successfully merged PR #%d", pr_number)
        return True
    except Exception as e:
        logger.error("Failed to merge PR #%d: %s", pr_number, e)
        return False


def fix_on_branch(pr_number: int) -> bool:
    """Attempt to fix failing tests on a PR branch.

    This is a placeholder for auto-fix logic. In practice, this would:
    - Analyze test failures
    - Make appropriate code changes
    - Commit and push the fix

    Args:
        pr_number: The PR number to fix.

    Returns:
        True if fixes were applied, False otherwise.
    """
    logger.info("Attempting to fix PR #%d", pr_number)
    # For now, just notify that manual intervention is needed
    notify_telegram(f"PR #{pr_number} has failing tests and needs manual fixing")
    return False


def process_open_prs() -> dict:
    """Process all open PRs: test and merge if passing.

    Returns:
        Dict with counts of merged, failed, and fixed PRs.
    """
    stats = {"merged": 0, "failed": 0, "fixed": 0, "total": 0}

    prs = get_open_prs()
    stats["total"] = len(prs)

    for pr in prs:
        pr_number = pr["number"]
        title = pr["title"]
        branch = pr["headRefName"]

        logger.info("Processing PR #%d: %s", pr_number, title)

        # Checkout and test
        if checkout_and_test_pr(pr_number, branch):
            # Tests pass - merge it
            if merge_pr(pr_number):
                stats["merged"] += 1
                notify_telegram(f"✅ Merged PR #{pr_number}: {title}")
        else:
            # Tests failed - try to fix
            if fix_on_branch(pr_number):
                stats["fixed"] += 1
            else:
                stats["failed"] += 1

    return stats


def process_open_issues() -> dict:
    """Process open issues by creating fix branches and PRs.

    Returns:
        Dict with counts of issues processed.
    """
    stats = {"processed": 0, "total": 0}

    issues = get_open_issues()
    stats["total"] = len(issues)

    for issue in issues:
        issue_number = issue["number"]
        title = issue["title"]

        logger.info("Found issue #%d: %s", issue_number, title)
        # For now, just log. Auto-fixing issues is complex and requires analysis.
        notify_telegram(f"📋 Open issue #{issue_number}: {title}")

    return stats


def run_maintenance_cycle() -> dict:
    """Run a single maintenance cycle.

    Returns:
        Dict with summary of all actions taken.
    """
    logger.info("Starting maintenance cycle")

    results = {
        "prs": process_open_prs(),
        "issues": process_open_issues(),
    }

    logger.info("Maintenance cycle complete: %s", results)
    return results


def maintenance_loop(interval: int = 300) -> None:
    """Run continuous maintenance loop.

    Args:
        interval: Seconds between maintenance cycles (default: 300 = 5 min).
    """
    logger.info("Starting maintenance loop with interval=%d seconds", interval)

    try:
        while True:
            try:
                results = run_maintenance_cycle()

                # Send summary if anything happened
                if results["prs"]["total"] > 0 or results["issues"]["total"] > 0:
                    prs_merged = results["prs"]["merged"]
                    prs_failed = results["prs"]["failed"]
                    issues_total = results["issues"]["total"]
                    summary = (
                        f"🔄 Maintenance cycle complete:\n"
                        f"  PRs: {prs_merged} merged, {prs_failed} failed\n"
                        f"  Issues: {issues_total} open"
                    )
                    notify_telegram(summary)

            except Exception as e:
                logger.exception("Error in maintenance cycle: %s", e)
                notify_telegram(f"⚠️ Maintenance cycle error: {e}")

            logger.info("Sleeping for %d seconds", interval)
            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Maintenance loop stopped by user")
        notify_telegram("🛑 Maintenance loop stopped")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gasclaw maintenance loop")
    parser.add_argument("--once", action="store_true", help="Run once and exit (don't loop)")
    parser.add_argument(
        "--interval", type=int, default=300, help="Seconds between cycles (default: 300)"
    )
    args = parser.parse_args()

    if args.once:
        results = run_maintenance_cycle()
        print(f"Results: {results}")
    else:
        maintenance_loop(interval=args.interval)
