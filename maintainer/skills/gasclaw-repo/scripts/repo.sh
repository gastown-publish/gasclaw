#!/bin/bash
set -euo pipefail

ACTION="${1:-commits}"
REPO="gastown-publish/gasclaw"
WORKDIR="/workspace/gasclaw"

case "$ACTION" in
    commits)
        COUNT="${2:-20}"
        git -C "$WORKDIR" log --oneline -"$COUNT"
        ;;
    pr-detail)
        NUM="${2:?Usage: repo.sh pr-detail <number>}"
        gh pr view "$NUM" --repo "$REPO" --json number,title,body,state,additions,deletions,changedFiles
        ;;
    create-issue)
        TITLE="${2:?Usage: repo.sh create-issue <title> [body]}"
        BODY="${3:-}"
        gh issue create --repo "$REPO" --title "$TITLE" --body "$BODY"
        ;;
    close-issue)
        NUM="${2:?Usage: repo.sh close-issue <number>}"
        gh issue close "$NUM" --repo "$REPO"
        ;;
    pull)
        cd "$WORKDIR"
        git checkout main 2>/dev/null || true
        git pull origin main
        echo "Updated to: $(git log --oneline -1)"
        ;;
    diff)
        git -C "$WORKDIR" diff --stat
        ;;
    *)
        echo "Unknown action: $ACTION"
        echo "Available: commits, pr-detail, create-issue, close-issue, pull, diff"
        exit 1
        ;;
esac
