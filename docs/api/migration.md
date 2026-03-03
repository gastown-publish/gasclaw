# migration.py

Migration utilities for transitioning from Gastown to gasclaw.

## Overview

This module provides functionality to detect existing Gastown installations and migrate their configuration to gasclaw format. It handles:

- Detection of classic Gastown setups (environment variables or config files)
- Backup creation before migration
- Configuration format conversion
- Interactive prompting for missing required values

## Classes

### `MigrationResult`

Result of a migration attempt.

```python
@dataclass
class MigrationResult
```

#### Attributes

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `success` | `bool` | — | Whether migration succeeded |
| `dry_run` | `bool` | — | Whether this was a dry run |
| `gastown_detected` | `bool` | — | Whether Gastown installation was detected |
| `backup_path` | `Path \| None` | `None` | Path to backup directory |
| `migrated_keys` | `list[str]` | `[]` | List of migrated configuration keys |
| `env_file_path` | `Path \| None` | `None` | Path to created env file |
| `error_message` | `str` | `""` | Error message if migration failed |

#### Methods

##### `summary()`

Return a human-readable summary of the migration.

```python
def summary(self) -> str
```

**Returns**: Formatted string with migration status and details

---

## Functions

### `detect_gastown_setup()`

Detect if Gastown is installed and configured.

Checks for:

1. `KIMI_API_KEY` environment variable (classic Gastown)
2. Gastown config files in `~/.gt` or `~/.gastown`

```python
def detect_gastown_setup(
    search_dirs: list[Path] | Path | None = None,
) -> dict[str, Any]
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `search_dirs` | `list[Path] \| Path \| None` | `None` | Directories to search for Gastown configs |

**Returns**: Dict with detection results including:

```python
{
    "detected": bool,           # Whether Gastown was found
    "source": str,              # "env_var" or "config_file"
    "message": str,             # Human-readable status message
    # If detected from env_var:
    "kimi_api_key": str,
    # If detected from config_file:
    "config_dir": str,
    "config": dict,
    # If not detected:
    "reason": str,
}
```

---

### `create_backup()`

Create a backup of the Gastown configuration.

```python
def create_backup(gastown_dir: Path) -> Path | None
```

**Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `gastown_dir` | `Path` | Path to the Gastown configuration directory |

**Returns**: Path to the backup directory, or `None` if backup failed

**Backup Naming**: `backup-gastown-{YYYYMMDD-HHMMSS}`

---

### `migrate_config()`

Migrate Gastown configuration to gasclaw format.

```python
def migrate_config(
    gastown_dir: Path | None = None,
    env_file: Path | None = None,
    interactive: bool = True,
) -> dict[str, Any]
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `gastown_dir` | `Path \| None` | `None` | Path to Gastown config directory |
| `env_file` | `Path \| None` | `None` | Path to write gasclaw .env file |
| `interactive` | `bool` | `True` | Whether to prompt for missing config |

**Returns**: Dict with migration results:

```python
{
    "success": bool,
    "migrated_keys": list[str],
    "env_file": str | None,        # Path to created env file
    "gastown_kimi_keys": str,      # Migrated key string
    "error": str | None,           # Error message if failed
}
```

**Behavior**:

1. Detects Gastown setup using `detect_gastown_setup()`
2. Converts key format (comma-separated → colon-separated)
3. Prompts for missing required configuration
4. Writes complete `.env` file with all variables

---

### `migrate()`

Migrate Gastown configuration to gasclaw.

This is the high-level migration function that orchestrates the entire process.

```python
def migrate(
    gastown_dir: Path | None = None,
    gasclaw_env_file: Path | None = None,
    dry_run: bool = False,
    interactive: bool = True,
) -> MigrationResult
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `gastown_dir` | `Path \| None` | `None` | Path to Gastown config directory |
| `gasclaw_env_file` | `Path \| None` | `None` | Path to write gasclaw .env file |
| `dry_run` | `bool` | `False` | If True, only detect and report, don't modify |
| `interactive` | `bool` | `True` | Whether to prompt for missing configuration |

**Returns**: `MigrationResult` with full details of the migration

**Migration Process**:

1. Detect Gastown installation
2. Create backup of existing config (if not dry run)
3. Migrate configuration
4. Write new `.env` file (if not dry run)
5. Return detailed results

---

## Internal Functions

### `_parse_gastown_keys()`

Convert Gastown key format to gasclaw format.

```python
def _parse_gastown_keys(key_value: str) -> str
```

Gastown used comma-separated keys, gasclaw uses colon-separated.

**Parameters**:

| Name | Type | Description |
|------|------|-------------|
| `key_value` | `str` | The key string from Gastown config |

**Returns**: Colon-separated keys for gasclaw

---

### `_prompt_for_missing_config()`

Prompt user for required gasclaw configuration.

```python
def _prompt_for_missing_config(interactive: bool = True) -> dict[str, str]
```

**Parameters**:

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `interactive` | `bool` | `True` | Whether to prompt interactively |

**Returns**: Dict with configuration values

**Prompts for**:

- `OPENCLAW_KIMI_KEY` (if not in environment)
- `TELEGRAM_BOT_TOKEN` (if not in environment)
- `TELEGRAM_OWNER_ID` (if not in environment)

---

## Constants

| Name | Value | Description |
|------|-------|-------------|
| `DEFAULT_GASTOWN_DIRS` | `[Path.home() / ".gt", Path.home() / ".gastown"]` | Default directories to search |
| `DEFAULT_GASCLAW_ENV` | `Path("/workspace/.env")` | Default path for gasclaw env file |

---

## Usage Examples

### Check if Gastown is Installed

```python
from gasclaw.migration import detect_gastown_setup

result = detect_gastown_setup()
if result["detected"]:
    print(f"Found Gastown: {result['message']}")
else:
    print("No Gastown installation detected")
```

### Dry Run Migration

```python
from gasclaw.migration import migrate

result = migrate(dry_run=True)
print(result.summary())
# Output: 🔄 DRY RUN - No changes were made
```

### Perform Migration

```python
from gasclaw.migration import migrate
from pathlib import Path

result = migrate(
    gastown_dir=Path.home() / ".gt",
    gasclaw_env_file=Path("/workspace/.env"),
    interactive=True
)

if result.success:
    print("Migration successful!")
    print(f"Backup at: {result.backup_path}")
    print(f"Config at: {result.env_file_path}")
else:
    print(f"Migration failed: {result.error_message}")
```

### Non-Interactive Migration

```python
from gasclaw.migration import migrate
import os

# Set required vars in environment
os.environ["OPENCLAW_KIMI_KEY"] = "sk-openclaw-key"
os.environ["TELEGRAM_BOT_TOKEN"] = "bot-token"
os.environ["TELEGRAM_OWNER_ID"] = "12345"

result = migrate(interactive=False)
print(result.summary())
```

---

## Migration Mapping

| Gastown | Gasclaw | Notes |
|---------|---------|-------|
| `KIMI_API_KEY` | `GASTOWN_KIMI_KEYS` | Format: comma → colon separated |
| — | `OPENCLAW_KIMI_KEY` | New required variable |
| — | `TELEGRAM_BOT_TOKEN` | New required variable |
| — | `TELEGRAM_OWNER_ID` | New required variable |

