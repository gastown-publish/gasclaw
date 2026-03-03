# Architecture

Gasclaw combines three components into a single autonomous maintenance system.

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Gasclaw                              │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Gastown    │  │   OpenClaw   │  │   KimiGas    │      │
│  │   (Agents)   │  │  (Overseer)  │  │  (Key Pool)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │              │
│         └─────────────────┼─────────────────┘              │
│                           │                                │
│                    ┌──────┴──────┐                        │
│                    │  Bootstrap  │                        │
│                    │   & Monitor │                        │
│                    └──────┬──────┘                        │
│                           │                                │
│                    ┌──────┴──────┐                        │
│                    │   Telegram  │                        │
│                    │  (Reports)  │                        │
│                    └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Gastown (Agents)

Gastown is the agent framework that runs AI workers.

### Components

- **Daemon**: Manages agent lifecycle
- **Mayor**: Overseer agent for high-level decisions
- **Crew**: Worker agents that perform tasks

### Key Pool

Each agent gets its own Kimi API key from `GASTOWN_KIMI_KEYS`:

```
~/.kimi-accounts/
├── 1/config.toml   # Key 1 for agent 1
├── 2/config.toml   # Key 2 for agent 2
└── 3/config.toml   # Key 3 for agent 3
```

## OpenClaw (Overseer)

OpenClaw monitors all agents and enforces compliance.

### Responsibilities

- Monitor agent health and activity
- Enforce activity benchmark (commits every hour)
- Rotate keys on rate limits
- Restart failed agents
- Handle Telegram communication

### Configuration

OpenClaw config at `~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "telegram": {
      "botToken": "...",
      "dmPolicy": "allowlist",
      "allowFrom": [999999999]
    }
  },
  "gateway": {
    "port": 18789,
    "auth": { "token": "..." }
  }
}
```

### Skills

Skills are installed to `~/.openclaw/skills/`:

- `gastown-health`: Health check commands
- `gastown-keys`: Key management commands
- `gastown-update`: Update commands
- `gastown-agents`: Agent control commands

## KimiGas (Key Pool)

KimiGas manages API keys with LRU rotation and rate-limit cooldown.

### Features

- **LRU Rotation**: Least-recently-used key is selected first
- **Cooldown**: Rate-limited keys are quarantined for 5 minutes
- **Separate Pools**: Agents and overseer have independent key pools

### Key States

```
Available ──► In Use ──► Rate Limited ──► Cooldown ──► Available
               │              │
               └──────────────┘ (auto-rotate on 429)
```

## Bootstrap Sequence

```
┌─────────────────┐
│  Load Config    │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Setup Kimi      │
│ Accounts        │
└────────┬────────┘
         ▼
┌─────────────────┐     ┌─────────────────┐
│ Install         │────►│  Start Dolt     │
│ Gastown         │     └────────┬────────┘
└─────────────────┘              ▼
                          ┌─────────────────┐
                          │ Configure       │
                          │ OpenClaw        │
                          └────────┬────────┘
                                   ▼
                          ┌─────────────────┐
                          │ Install Skills  │
                          └────────┬────────┘
                                   ▼
                          ┌─────────────────┐
                          │ Run Doctor      │
                          └────────┬────────┘
                                   ▼
                          ┌─────────────────┐
                          │ Start Services  │
                          │ (daemon, mayor) │
                          └────────┬────────┘
                                   ▼
                          ┌─────────────────┐
                          │ Start Monitor   │
                          │ Loop            │
                          └─────────────────┘
```

## Health Monitoring

The monitor loop runs continuously:

```python
while True:
    report = check_health()      # Check all services
    activity = check_activity()  # Check git activity

    if not activity.compliant:
        notify_telegram("ACTIVITY ALERT")

    if any_service_unhealthy:
        notify_telegram("SERVICE DOWN")

    sleep(interval)
```

### Health Checks

| Service | Check Method |
|---------|-------------|
| Dolt | `dolt sql -q "SELECT 1"` |
| Daemon | `gt daemon status` |
| Mayor | `gt mayor status` |
| OpenClaw | `GET http://localhost:18789/health` |
| Agents | `gt status --agents` |

## Communication Flow

```
GitHub API ◄────► Gasclaw ◄────► OpenClaw ◄────► Telegram
                      │
                      ▼
                Gastown Agents
                      │
                      ▼
                 Dolt (State)
```

1. **GitHub**: PRs, issues, commits
2. **Gasclaw**: Orchestrates actions
3. **OpenClaw**: Makes decisions, sends Telegram updates
4. **Telegram**: User notifications and commands
5. **Gastown**: Executes tasks
6. **Dolt**: Stores all state via beads

## Data Flow

### State Management

All state is stored in Dolt via beads (bd CLI):

```bash
bd create --name "task-123" --content "Fix bug"
bd list
bd search --query "bug"
bd close --name "task-123"
```

### Configuration

- Environment variables: Runtime config
- `~/.openclaw/openclaw.json`: OpenClaw config
- `~/.kimi-accounts/`: API key configs
- `/workspace/gt/`: Gastown installation

## Security

- API keys never logged or exposed
- Telegram allowlist restricts access
- Auth tokens for gateway authentication
- Separate key pools prevent cascade failures
