"""CI failure monitoring for GitHub Actions.

Monitors GitHub Actions workflow runs and auto-creates issues for failures.
State is persisted to avoid duplicate issues.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# State file location (persisted across restarts)
DEFAULT_STATE_FILE = "/workspace/state/ci_failures.json"
MAX_HISTORY_SIZE = 100  # Keep last 100 failure IDs to limit file size


@dataclass
class CIFailure:
    """Represents a CI workflow failure."""

    run_id: str
    workflow_name: str
    url: str
    started_at: str

    def unique_id(self) -> str:
        """Generate unique identifier for deduplication."""
        return f"{self.workflow_name}:{self.run_id}"


def get_failed_workflows(repo: str) -> list[CIFailure]:
    """Get list of failed workflow runs from GitHub CLI.

    Args:
        repo: Repository in format "owner/repo"

    Returns:
        List of CIFailure objects for failed runs
    """
    cmd = [
        "gh", "run", "list",
        "--repo", repo,
        "--status", "failure",
        "--json", "databaseId,name,status,conclusion,url,startedAt",
        "--limit", "20"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            logger.warning("gh run list failed: %s", result.stderr)
            return []

        runs = json.loads(result.stdout)
        return [
            CIFailure(
                run_id=str(run.get("databaseId", "")),
                workflow_name=run.get("name", "Unknown Workflow"),
                url=run.get("url", ""),
                started_at=run.get("startedAt", "")
            )
            for run in runs
            if run.get("conclusion") == "failure"
        ]

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse gh output: %s", e)
        return []
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to get failed workflows: %s", e)
        return []


def load_seen_failures(state_file: str | None = None) -> set[str]:
    """Load set of previously seen failure IDs.

    Args:
        state_file: Path to state file. Uses DEFAULT_STATE_FILE if not specified.

    Returns:
        Set of failure unique IDs that have been processed
    """
    path = Path(state_file or DEFAULT_STATE_FILE)

    if not path.exists():
        return set()

    try:
        with open(path) as f:
            data = json.load(f)
            return set(data.get("seen", []))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load seen failures: %s", e)
        return set()


def save_seen_failures(seen: set[str], state_file: str | None = None) -> None:
    """Save set of seen failure IDs to state file.

    Args:
        seen: Set of failure unique IDs
        state_file: Path to state file. Uses DEFAULT_STATE_FILE if not specified.
    """
    path = Path(state_file or DEFAULT_STATE_FILE)

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(path, "w") as f:
            json.dump({"seen": sorted(seen)}, f, indent=2)
    except OSError as e:
        logger.warning("Failed to save seen failures: %s", e)


def is_duplicate_issue(failure_id: str, seen: set[str]) -> bool:
    """Check if a failure has already been reported.

    Args:
        failure_id: Unique identifier for the failure
        seen: Set of previously seen failure IDs

    Returns:
        True if failure was already reported
    """
    return failure_id in seen


def create_failure_issue(repo: str, failure: CIFailure) -> bool:
    """Create a GitHub issue for a CI failure.

    Args:
        repo: Repository in format "owner/repo"
        failure: CIFailure to report

    Returns:
        True if issue was created successfully
    """
    title = f"CI Failure: {failure.workflow_name} (run #{failure.run_id})"

    body = f"""## CI Workflow Failure

**Workflow:** {failure.workflow_name}
**Run ID:** {failure.run_id}
**Started:** {failure.started_at}
**URL:** {failure.url}

This issue was automatically created by the Gasclaw maintainer bot  # noqa: E501
when a GitHub Actions workflow failed.

---
*This is an automated message. Please investigate the failure and close this issue when resolved.*
"""

    cmd = [
        "gh", "issue", "create",
        "--repo", repo,
        "--title", title,
        "--body", body,
        "--label", "ci-failure"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            logger.info("Created issue for %s run %s", failure.workflow_name, failure.run_id)
            return True
        else:
            logger.warning("Failed to create issue: %s", result.stderr)
            return False

    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to create issue: %s", e)
        return False


def format_failure_message(failure: CIFailure) -> str:
    """Format a failure notification for Telegram.

    Args:
        failure: CIFailure to format

    Returns:
        Markdown-formatted message
    """
    return (
        f"🔴 *CI Failure: {failure.workflow_name}*\n"
        f"Run: #{failure.run_id}\n"
        f"[View on GitHub]({failure.url})"
    )


def check_ci_failures(
    repo: str,
    state_file: str | None = None,
    send_notification: Callable[[str], None] | None = None
) -> dict[str, int]:
    """Check for CI failures and create issues for new ones.

    Args:
        repo: Repository in format "owner/repo"
        state_file: Path to state file for persistence
        send_notification: Optional callback for notifications (e.g., Telegram)

    Returns:
        Dict with counts: {"checked": N, "new": N, "duplicates": N}
    """
    result = {"checked": 0, "new": 0, "duplicates": 0}

    # Get current failures
    failures = get_failed_workflows(repo)
    result["checked"] = len(failures)

    if not failures:
        logger.debug("No CI failures found")
        return result

    # Load previously seen failures
    seen = load_seen_failures(state_file)
    new_seen = seen.copy()

    # Process each failure
    for failure in failures:
        failure_id = failure.run_id  # Use run_id for deduplication

        if is_duplicate_issue(failure_id, seen):
            result["duplicates"] += 1
            logger.debug("Skipping duplicate failure: %s", failure_id)
            new_seen.add(failure_id)  # Keep in history
            continue

        # Create issue for new failure
        if create_failure_issue(repo, failure):
            result["new"] += 1
            new_seen.add(failure_id)

            # Send notification if callback provided
            if send_notification:
                try:
                    send_notification(format_failure_message(failure))
                except Exception as e:
                    logger.warning("Failed to send notification: %s", e)

    # Limit history size
    if len(new_seen) > MAX_HISTORY_SIZE:
        # Keep most recent (sorted by ID which is roughly chronological)
        new_seen = set(sorted(new_seen)[-MAX_HISTORY_SIZE:])

    # Save updated history
    save_seen_failures(new_seen, state_file)

    return result
