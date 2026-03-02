# Bootstrap API

The bootstrap module handles the startup sequence for Gasclaw.

## Functions

### `bootstrap(config, gt_root)`

Run the full bootstrap sequence.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `config` | `GasclawConfig` | Validated gasclaw configuration |
| `gt_root` | `Path` | Where to install Gastown (default: `/workspace/gt`) |

**Raises:**

- `RuntimeError`: If bootstrap fails, after attempting rollback

**Bootstrap Sequence:**

1. Setup Kimi accounts for Gastown agents
2. Write agent config
3. Install Gastown
4. Start Dolt
5. Configure OpenClaw
6. Install skills
7. Run openclaw doctor
8. Start OpenClaw gateway
9. Start gt daemon
10. Start mayor agent
11. Send startup notification

**Example:**

```python
from gasclaw.bootstrap import bootstrap
from gasclaw.config import load_config

config = load_config()
bootstrap(config)
```

---

### `monitor_loop(config, interval)`

Foreground health monitor loop.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `config` | `GasclawConfig` | Gasclaw configuration |
| `interval` | `int \| None` | Seconds between checks (default from config) |

**Behavior:**

- Runs health checks at regular intervals
- Sends Telegram notifications for:
  - Activity violations (no commits within deadline)
  - Service failures (dolt, daemon, mayor down)
- Continues until interrupted (Ctrl+C)

**Example:**

```python
from gasclaw.bootstrap import monitor_loop
from gasclaw.config import load_config

config = load_config()
monitor_loop(config)  # Uses config.monitor_interval
```
