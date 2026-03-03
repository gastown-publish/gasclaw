# Health API

Health checks for all gasclaw subsystems.

## Classes

### `HealthReport`

Complete health report for the gasclaw system.

**Attributes:**

| Name | Type | Description |
|------|------|-------------|
| `dolt` | `str` | Dolt status: "healthy", "unhealthy", or "unknown" |
| `daemon` | `str` | Daemon status: "healthy", "unhealthy", or "unknown" |
| `mayor` | `str` | Mayor status: "healthy", "unhealthy", or "unknown" |
| `openclaw` | `str` | OpenClaw status: "healthy", "unhealthy", or "unknown" |
| `openclaw_doctor` | `str` | Doctor status: "healthy" or "unhealthy" |
| `agents` | `list[str]` | List of active agent names |
| `key_pool` | `dict` | Key pool statistics |
| `activity` | `dict` | Activity compliance data |

**Methods:**

#### `summary()`

Return human-readable summary string.

```python
report = check_health()
print(report.summary())
# Dolt: healthy
# Daemon: healthy
# Mayor: healthy
# OpenClaw: healthy
# Agents: 3 active (mayor, crew-1, crew-2)
```

---

## Functions

### `check_health(gateway_port, dolt_port)`

Run all health checks and return a complete report.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `gateway_port` | `int` | 18789 | OpenClaw gateway port |
| `dolt_port` | `int` | 3307 | Dolt SQL server port |

**Returns:**

- `HealthReport`: Complete health report

**Example:**

```python
from gasclaw.health import check_health

report = check_health()
if report.dolt == "unhealthy":
    print("Dolt is down!")
if len(report.agents) < 3:
    print("Not enough agents running")
```

---

### `check_agent_activity(project_dir, deadline_seconds)`

Check if there has been recent git activity.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `project_dir` | `str` | "/project" | Directory containing git repo |
| `deadline_seconds` | `int` | 3600 | Max allowed time since last activity |

**Returns:**

```python
{
    "last_commit_age": 1800,  # seconds since last commit
    "compliant": True,        # within deadline
    "error": None             # or error message
}
```

**Example:**

```python
from gasclaw.health import check_agent_activity

activity = check_agent_activity(
    project_dir="/workspace/gasclaw",
    deadline_seconds=3600
)

if not activity["compliant"]:
    print(f"No commits in {activity['last_commit_age']}s!")
```
