---
name: monitor-pr-ci
description: Monitor PR CI checks and review comments, auto-fix failures and address feedback
metadata:
  openclaw:
    emoji: "\U0001F6A6"
    os:
      - linux
    requires:
      bins:
        - gh
        - git
parameters:
  pr:
    type: string
    description: PR number or URL to monitor (default: current branch PR)
    required: false
  max-iterations:
    type: string
    description: Maximum polling iterations (default: 30)
    required: false
  interval:
    type: string
    description: Polling interval in seconds (default: 60)
    required: false
---

# CI Monitor & PR Babysitter

Monitor a PR's CI checks and review comments. Automatically fix CI failures and address reviewer feedback.

## Overview

This skill watches a PR until it is merged or reaches the iteration limit. Each iteration:
1. Polls CI check status
2. Polls review comments and inline suggestions
3. If CI fails: fetches logs, analyzes the failure, applies a fix, pushes
4. If new review comments: categorizes, fixes code, replies, resolves threads

## Setup

Ensure `gh` is authenticated and the repo is cloned locally:
```bash
gh auth status
git remote -v
```

## Workflow

### Step 1: Identify the PR

If no PR number is given, detect from the current branch:
```bash
PR_NUMBER=$(gh pr view --json number -q '.number' 2>/dev/null)
```

If a PR number or URL is provided, use it directly.

### Step 2: Polling Loop

Repeat up to `max-iterations` times (default 30), sleeping `interval` seconds (default 60) between iterations:

#### 2a. Check CI Status

```bash
gh pr checks "$PR_NUMBER" --json name,state,conclusion,detailsUrl
```

Categorize results:
- **COMPLETED + SUCCESS**: No action needed
- **IN_PROGRESS / QUEUED**: Wait for next iteration
- **COMPLETED + FAILURE**: Needs investigation (go to Step 3)

#### 2b. Check Reviews and Comments

```bash
gh pr view "$PR_NUMBER" --json reviews,reviewRequests,comments
gh api repos/{owner}/{repo}/pulls/{pr}/comments
```

Categorize comments:
- **Actionable**: Code changes requested, bugs found, style issues
- **Questions**: Need a reply but no code change
- **Praise/Acknowledgment**: Reply with thanks, no code change
- **Resolved**: Already addressed, skip

### Step 3: Fix CI Failures

For each failing check:

1. **Fetch logs**: Use the `detailsUrl` or GitHub Actions API:
   ```bash
   # Get the failed run ID
   RUN_ID=$(gh api repos/{owner}/{repo}/actions/runs --jq '.workflow_runs[] | select(.head_sha=="'$(git rev-parse HEAD)'") | .id' | head -1)
   # Get failed job logs
   gh run view "$RUN_ID" --log-failed
   ```

2. **Analyze the failure**: Read the log output. Common categories:
   - **Lint errors**: Fix formatting/style issues
   - **Type errors**: Fix type mismatches
   - **Test failures**: Read the failing test, understand the assertion, fix code or test
   - **Build errors**: Fix import/dependency issues
   - **Timeout**: Investigate slow operations

3. **Apply the fix**: Edit the relevant files based on the error analysis.

4. **Commit and push**:
   ```bash
   git add -A
   git commit -m "fix(ci): <description of what was fixed>"
   git push
   ```

5. **Wait for CI to re-run** on the next polling iteration.

### Step 4: Address Review Comments

For each actionable comment:

1. **Read the comment** and the surrounding code context.

2. **Apply the requested change** to the relevant file(s).

3. **Reply to the comment** acknowledging the fix:
   ```bash
   gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies \
     -f body="Fixed in $(git rev-parse --short HEAD). <brief explanation>"
   ```

4. **Resolve the thread** if you have permission:
   ```bash
   gh api graphql -f query='
     mutation {
       resolveReviewThread(input: {threadId: "<thread_id>"}) {
         thread { isResolved }
       }
     }'
   ```

5. **Commit and push** all fixes together:
   ```bash
   git add -A
   git commit -m "fix(review): address review feedback"
   git push
   ```

### Step 5: Exit Conditions

Stop polling when any of these are true:
- PR is merged
- PR is closed
- All CI checks pass AND no unresolved review comments
- Max iterations reached

Report final status:
```bash
gh pr view "$PR_NUMBER" --json state,mergeable,statusCheckRollup,reviews
```

## Error Handling

- If `gh` commands fail with auth errors, re-authenticate: `gh auth login`
- If push is rejected (force-push protection), pull and rebase first
- If a fix attempt makes things worse (new CI failure), revert the commit and try a different approach
- Never force-push to a shared branch without explicit approval

## Iteration Limits

- Default max iterations: 30
- Default polling interval: 60 seconds
- Total max runtime: ~30 minutes by default
- If the fix-push-wait cycle exceeds 5 consecutive failures on the same check, stop and report the issue

## Output

At the end of each iteration, print a status summary:
```
[Iteration 3/30] PR #42
  CI: 4/5 passing, 1 in progress (build)
  Reviews: 2 resolved, 1 pending
  Action: Waiting for build check to complete
```

At completion:
```
PR #42 — All checks passing, all reviews addressed
  Total iterations: 7
  Fixes applied: 3 (2 CI, 1 review)
  Ready for merge
```
