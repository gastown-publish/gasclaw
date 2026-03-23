---
name: commit-helper
description: Create well-structured conventional commit messages from staged changes
metadata:
  openclaw:
    emoji: "\U0001F4DD"
    os:
      - linux
    requires:
      bins:
        - git
parameters:
  amend:
    type: string
    description: "Amend the previous commit instead of creating new: true or false (default: false)"
    required: false
---

# Commit Helper

Analyze staged changes and create a well-structured conventional commit message.

## Commit Format

```
<type>(<scope>): <summary>

<body>

<footer>
```

### Type

Determine from the staged changes:

| Type | Condition |
|------|-----------|
| `feat` | New files, new functions, new capabilities |
| `fix` | Bug fixes, error handling corrections |
| `perf` | Performance optimizations |
| `test` | Test files only (new or updated) |
| `docs` | Documentation/markdown only |
| `refactor` | Restructuring without behavior change |
| `build` | Build configs, Makefile, Dockerfile |
| `ci` | CI/CD files (.github/workflows, etc.) |
| `chore` | Dependency updates, config tweaks |

### Scope

Derive from changed files:
- If all changes are in one directory: use that directory name
- If changes span a module: use the module name
- If changes are cross-cutting: omit scope or use a descriptive word

### Summary Line

- Imperative mood: "add" not "added" or "adds"
- Lowercase first letter
- No trailing period
- Max 50 characters
- Completes the sentence: "This commit will ___"

### Body (optional but recommended for non-trivial changes)

- Separated from summary by a blank line
- Wrap at 72 characters
- Explain **what** and **why**, not **how** (the diff shows how)
- Use bullet points for multiple changes

### Footer (optional)

- `Fixes #<issue>` for bug fix PRs
- `Related to #<issue>` for feature work
- `BREAKING CHANGE: <description>` for breaking changes

## Workflow

### Step 1: Analyze Staged Changes

```bash
# See what's staged
git diff --cached --stat

# See the actual changes
git diff --cached

# See untracked files (might need staging)
git status --short
```

### Step 2: Determine Commit Type and Scope

Read the staged diff and categorize:
1. What type of change is this? (feat, fix, refactor, etc.)
2. What area is affected? (directory, module, component)
3. What is the primary intent of the change?

### Step 3: Write the Message

Compose the commit message following the format above.

### Step 4: Create the Commit

```bash
git commit -m "<type>(<scope>): <summary>

<body>

<footer>"
```

Or if amending:
```bash
git commit --amend -m "<type>(<scope>): <summary>

<body>

<footer>"
```

### Step 5: Verify

```bash
# Check the commit was created
git log --oneline -1

# Verify the full message
git log -1 --format="%B"
```

## Examples

**Simple feature**:
```
feat(cli): add verbose flag to status command
```

**Bug fix with body**:
```
fix(proxy): handle connection timeout during key rotation

The key rotation loop was not catching ConnectionError exceptions,
causing the entire health monitor to crash when the upstream API
was temporarily unreachable.

Fixes #23
```

**Multi-file refactor**:
```
refactor(bootstrap): extract service startup into dedicated functions

- Move dolt startup to _start_dolt()
- Move daemon startup to _start_daemon()
- Move mayor startup to _start_mayor()

Each function now handles its own retry logic and error reporting,
making the bootstrap sequence easier to test and debug.
```

**Test addition**:
```
test(health): add edge cases for activity compliance check

Cover scenarios where:
- Agent has no commits at all
- Agent's last commit is exactly at the deadline
- Clock skew between agent and server
```

## Rules

1. **Never commit unstaged changes**: Only describe what's in `git diff --cached`
2. **One logical change per commit**: If staged changes are unrelated, suggest splitting
3. **No WIP commits on shared branches**: If changes are incomplete, suggest a more descriptive message
4. **Reference issues**: Always link to issues when applicable
5. **Check before committing**: Verify tests pass with `make test` if available
