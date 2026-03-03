# Config API

Configuration loading and validation from environment variables.

## Classes

### `GasclawConfig`

Dataclass representing Gasclaw configuration.

**Attributes:**

| Name | Type | Description |
|------|------|-------------|
| `gastown_kimi_keys` | `list[str]` | Colon-separated Kimi keys for Gastown |
| `openclaw_kimi_key` | `str` | Kimi key for OpenClaw |
| `telegram_bot_token` | `str` | Telegram bot token |
| `telegram_owner_id` | `str` | Telegram owner user ID |
| `gt_rig_url` | `str` | Git URL or path for rig (default: `/project`) |
| `project_dir` | `str` | Directory for git activity checks (default: `/project`) |
| `gt_agent_count` | `int` | Number of crew workers (default: 6) |
| `monitor_interval` | `int` | Health check interval in seconds (default: 300) |
| `activity_deadline` | `int` | Max seconds between commits (default: 3600) |
| `dolt_port` | `int` | Dolt SQL server port (default: 3307) |

**Validation:**

- `telegram_owner_id` must be numeric
- `project_dir` should be absolute path
- `gt_rig_url` should be path or URL

---

## Functions

### `load_config()`

Load and validate configuration from environment variables.

**Returns:**

- `GasclawConfig`: Validated configuration object

**Raises:**

- `ValueError`: If required environment variables are not set

**Example:**

```python
from gasclaw.config import load_config

config = load_config()
print(f"Loaded {len(config.gastown_kimi_keys)} keys")
print(f"Monitor interval: {config.monitor_interval}s")
```

**Environment Variables:**

```bash
# Required
export GASTOWN_KIMI_KEYS="sk-key1:sk-key2"
export OPENCLAW_KIMI_KEY="sk-overseer"
export TELEGRAM_BOT_TOKEN="123:ABC"
export TELEGRAM_OWNER_ID="999999999"

# Optional
export GT_RIG_URL="/project"
export GT_AGENT_COUNT=6
export MONITOR_INTERVAL=300
export ACTIVITY_DEADLINE=3600
export DOLT_PORT=3307
```
