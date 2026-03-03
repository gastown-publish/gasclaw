# maintenance.py

Automated maintenance loop for the gasclaw repository.

## Overview

This module provides continuous maintenance capabilities for the gasclaw project:

- Check and merge open PRs automatically
- Fix open issues
- Improve test coverage
- Maintain code quality

Can be run as a standalone script or imported as a module.

## Classes

### `CommandNotFoundError`

Raised when a command binary is not found in PATH.

```python
class CommandNotFoundError(subprocess.CalledProcessError)
```

**Inheritance**: `subprocess.CalledProcessError`

#### Constructor

```python
def __init__(cmd: list[str]) -> None
```

**Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `cmd` | `list[str]` | The command that was not found |

**Attributes**:

| Name | Type | Description |
|------|------|-------------|
| `binary` | `str` | The binary name that was not found |

---

## Functions

### `run_command()`

Run a shell command and return the result.

```python
def run_command(
    cmd: list[str],
    *,
    check: bool = True,
    timeout: int = 120
) -> subprocess.CompletedProcess[str]
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `cmd` | `list[str]` | — | Command and arguments as a list |
| `check` | `bool` | `True` | If True, raise CalledProcessError on non-zero exit |
| `timeout` | `int` | `120` | Max seconds to wait for command |

**Returns**: `CompletedProcess` with `returncode`, `stdout`, `stderr`

**Raises**:

- `CommandNotFoundError`: If `check=True` and command binary is not found
- `subprocess.CalledProcessError`: If `check=True` and command fails
- `subprocess.TimeoutExpired`: If command times out

---

### `get_open_prs()`

Get list of open PRs from GitHub.

```python
def get_open_prs(timeout: int = 120) -> list[dict[str, Any]]
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `timeout` | `int` | `120` | Max seconds to wait for the command |

**Returns**: List of PR dicts with `number`, `title`, `headRefName`, and `author`

---

### `get_open_issues()`

Get list of open issues from GitHub.

```python
def get_open_issues(timeout: int = 120) -> list[dict[str, Any]]
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `timeout` | `int` | `120` | Max seconds to wait for the command |

**Returns**: List of issue dicts with `number` and `title`

---

### `checkout_and_test_pr()`

Checkout a PR branch and run tests.

```python
def checkout_and_test_pr(pr_number: int, branch: str) -> bool
```

**Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `pr_number` | `int` | The PR number |
| `branch` | `str` | The branch name to checkout |

**Returns**: `True` if tests pass, `False` otherwise

---

### `merge_pr()`

Merge a PR using squash merge.

```python
def merge_pr(pr_number: int) -> bool
```

**Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `pr_number` | `int` | The PR number to merge |

**Returns**: `True` if merge succeeded, `False` otherwise

---

### `process_open_prs()`

Process all open PRs: test and merge if passing.

```python
def process_open_prs() -> dict[str, Any]
```

**Returns**: Dict with counts of `merged`, `failed`, and `fixed` PRs, plus `total`

**Return Structure**:

```python
{
    "merged": int,   # Number of PRs successfully merged
    "failed": int,   # Number of PRs with failing tests
    "fixed": int,    # Number of PRs auto-fixed (placeholder)
    "total": int     # Total PRs processed
}
```

---

### `process_open_issues()`

Process open issues by creating fix branches and PRs.

```python
def process_open_issues() -> dict[str, Any]
```

**Returns**: Dict with counts of issues processed

**Return Structure**:

```python
{
    "processed": int,  # Number of issues processed
    "total": int       # Total open issues found
}
```

---

### `run_maintenance_cycle()`

Run a single maintenance cycle.

```python
def run_maintenance_cycle() -> dict[str, Any]
```

**Returns**: Dict with summary of all actions taken

**Return Structure**:

```python
{
    "prs": {
        "merged": int,
        "failed": int,
        "fixed": int,
        "total": int
    },
    "issues": {
        "processed": int,
        "total": int
    }
}
```

---

### `maintenance_loop()`

Run continuous maintenance loop.

```python
def maintenance_loop(interval: int = 300) -> None
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `interval` | `int` | `300` | Seconds between maintenance cycles |

**Behavior**:

- Runs indefinitely until interrupted
- Sends Telegram notifications for PR merges and errors
- Catches exceptions and continues looping
- Handles `KeyboardInterrupt` gracefully

---

### `main()`

Run the maintenance script entry point.

```python
def main(args: list[str] | None = None) -> None
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `args` | `list[str] \| None` | `None` | Command line arguments (defaults to `sys.argv[1:]`)

**Command Line Usage**:

```bash
# Run maintenance once
python -m gasclaw.maintenance --once

# Run continuous loop with custom interval
python -m gasclaw.maintenance --interval 600
```

---

## Usage Examples

### Run a Single Maintenance Cycle

```python
from gasclaw.maintenance import run_maintenance_cycle

results = run_maintenance_cycle()
print(f"Merged: {results['prs']['merged']}")
print(f"Failed: {results['prs']['failed']}")
```

### Get Open PRs

```python
from gasclaw.maintenance import get_open_prs

prs = get_open_prs()
for pr in prs:
    print(f"#{pr['number']}: {pr['title']}")
```

### Run Continuous Loop

```python
from gasclaw.maintenance import maintenance_loop

# Run every 5 minutes (default)
maintenance_loop()

# Run every 10 minutes
maintenance_loop(interval=600)
```

---

## Constants

| Name | Value | Description |
|------|-------|-------------|
| `REPO` | `"gastown-publish/gasclaw"` | GitHub repository identifier |
