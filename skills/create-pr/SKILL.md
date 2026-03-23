---
name: create-pr
description: Create a well-structured PR with conventional commit title and descriptive body
metadata:
  openclaw:
    emoji: "\U0001F4E4"
    os:
      - linux
    requires:
      bins:
        - gh
        - git
parameters:
  base:
    type: string
    description: Base branch to merge into (default: main)
    required: false
  draft:
    type: string
    description: "Create as draft PR: true or false (default: false)"
    required: false
---

# Create PR with Conventional Commits

Create a pull request with a properly formatted conventional commit title and a structured body.

## Title Format

PR titles MUST follow conventional commit format:
```
<type>(<scope>): <summary>
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `perf` | Performance improvement |
| `test` | Adding or updating tests only |
| `docs` | Documentation changes only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `build` | Build system or dependency changes |
| `ci` | CI/CD configuration changes |
| `chore` | Maintenance tasks (deps, configs) |

### Scope

The scope should be the primary module or area affected:
- Use the directory name or package name (e.g., `cli`, `health`, `proxy`, `bootstrap`)
- For cross-cutting changes, use a descriptive scope (e.g., `deps`, `config`)
- Scope is optional but recommended

### Summary

- Use imperative mood ("add feature" not "added feature" or "adds feature")
- No capitalization of first letter
- No period at the end
- Keep under 50 characters

**Examples**:
```
feat(cli): add status subcommand
fix(proxy): handle timeout in key rotation
test(health): add compliance deadline edge cases
refactor(bootstrap): extract service startup into helpers
ci: add Python 3.12 to test matrix
```

## Workflow

### Step 1: Analyze Changes

```bash
# Get current branch
BRANCH=$(git branch --show-current)

# Get base branch (default: main)
BASE="${base:-main}"

# Get commit log since divergence
git log "$BASE".."$BRANCH" --oneline

# Get full diff summary
git diff "$BASE"..."$BRANCH" --stat

# Get detailed diff
git diff "$BASE"..."$BRANCH"
```

### Step 2: Determine Type and Scope

Based on the changes:
1. Read all commits and the diff
2. Determine the primary type (feat, fix, etc.)
3. Identify the main scope from affected directories/files
4. Write a concise summary in imperative mood

### Step 3: Generate PR Body

Use this template:

```markdown
## Summary

<1-3 bullet points describing what changed and why>

## Changes

- <specific change 1>
- <specific change 2>
- ...

## Test Plan

- [ ] <how to verify change 1>
- [ ] <how to verify change 2>
- [ ] All existing tests pass (`make test`)
```

If the PR fixes an issue, add: `Fixes #<issue_number>`

### Step 4: Create the PR

```bash
# Push branch to remote
git push -u origin "$BRANCH"

# Create PR
gh pr create \
  --base "$BASE" \
  --title "<type>(<scope>): <summary>" \
  --body "$BODY"
```

If `draft` is true:
```bash
gh pr create \
  --base "$BASE" \
  --title "<type>(<scope>): <summary>" \
  --body "$BODY" \
  --draft
```

### Step 5: Verify

```bash
# Confirm PR was created
gh pr view --json number,url,title,state

# Check CI was triggered
gh pr checks
```

Print the PR URL at the end.

## Rules

1. **Never skip the body**: Every PR needs a summary and test plan
2. **One concern per PR**: If changes span unrelated areas, suggest splitting
3. **Link issues**: Reference related issues with `Fixes #N` or `Related to #N`
4. **Label appropriately**: Add labels if the repo uses them
5. **Keep PRs small**: If the diff is >500 lines, consider splitting into smaller PRs
