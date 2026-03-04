# Architecture

Gasclaw combines three components into a single autonomous maintenance system. All agents use Kimi K2.5 as their LLM backend via Claude Code's agentic interface.

## Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                          Gasclaw                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Gastown    │  │   OpenClaw   │  │   KimiGas    │          │
│  │   (Agents)   │  │  (Overseer)  │  │  (Key Pool)  │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                    │
│         └─────────────────┼─────────────────┘                    │
│                           │                                      │
│                    ┌──────┴──────┐                                │
│                    │  Bootstrap  │                                │
│                    │   & Monitor │                                │
│                    └──────┬──────┘                                │
│                           │                                      │
│                    ┌──────┴──────┐                                │
│                    │   Telegram  │                                │
│                    │  (Reports)  │                                │
│                    └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

## Gastown (Agents)

Gastown ([github.com/steveyegge/gastown](https://github.com/steveyegge/gastown)) is the Go-based agent framework. Installed via `go install`, it provides the `gt` CLI.

### Components

- **Daemon**: Manages agent lifecycle (start, stop, monitor)
- **Mayor**: Overseer agent for high-level coordination
- **Crew**: Worker agents that execute tasks in parallel
- **Deacon, Witness, Refinery**: Supporting services

### Agent Command Flow

Every agent process invokes `claude` (Claude Code CLI). The environment is configured so `claude` talks to Kimi K2.5 instead of Anthropic:

```
gt daemon ──► spawns claude process
                 │
                 ├── ANTHROPIC_BASE_URL = https://api.kimi.com/coding/
                 ├── ANTHROPIC_API_KEY  = <kimi-key-from-pool>
                 └── CLAUDE_CONFIG_DIR  = ~/.claude-kimigas
                         │
                         └── .claude.json (bypassPermissionsModeAccepted: true)
```

Permission bypass is via the Claude config file — not `--dangerously-skip-permissions` (which fails under root).

### Key Distribution

Each agent gets its own Kimi API key from the `GASTOWN_KIMI_KEYS` pool:

```
~/.kimi-accounts/
├── 1/config.toml   # Key 1 for agent 1
├── 2/config.toml   # Key 2 for agent 2
└── 3/config.toml   # Key 3 for agent 3
```

## OpenClaw (Overseer)

OpenClaw runs embedded in the container. It monitors all agents and communicates via Telegram using its **native Telegram provider** (not polling or wrappers).

### Responsibilities

- Monitor agent health and activity
- Enforce activity benchmark (commits every hour)
- Rotate keys on rate limits
- Restart failed agents
- Handle Telegram communication (DMs and groups)

### Configuration

OpenClaw config at `~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "...",
      "dmPolicy": "open",
      "allowFrom": ["*"],
      "groupPolicy": "open",
      "streaming": "off"
    }
  },
  "messages": {
    "ackReactionScope": "all"
  },
  "gateway": {
    "port": 18789,
    "auth": { "mode": "token", "token": "..." }
  }
}
```

Key policies:
- `dmPolicy: "open"` with `allowFrom: ["*"]` — accepts all DMs
- `groupPolicy: "open"` — accepts all group messages
- `ackReactionScope: "all"` — responds to all messages without requiring @mention

### Skills

Skills are installed to `~/.openclaw/skills/`:

| Skill | Purpose |
|-------|---------|
| `gastown-health` | Health check commands |
| `gastown-keys` | Key management commands |
| `gastown-update` | Update commands |
| `gastown-agents` | Agent control commands |
| `ais-orchestrator` | Multi-agent tmux orchestration |

## KimiGas (Key Pool)

KimiGas manages API keys with LRU rotation and rate-limit cooldown.

### Features

- **LRU Rotation**: Least-recently-used key is selected first
- **Cooldown**: Rate-limited keys are quarantined for 5 minutes (300s)
- **Separate Pools**: Agents (`GASTOWN_KIMI_KEYS`) and overseer (`OPENCLAW_KIMI_KEY`) have independent pools
- **Graceful Degradation**: If all keys are rate-limited, returns the key closest to cooldown expiry
- **Privacy**: Keys tracked by BLAKE2b hash, never stored in plaintext in state files

### Key States

```
Available ──► In Use ──► Rate Limited ──► Cooldown (5 min) ──► Available
               │              │
               └──────────────┘ (auto-rotate on 429)
```

## Bootstrap Sequence

The 10-step startup orchestration in `bootstrap.py`:

```
┌─────────────────┐
│ 1. Setup Kimi   │  Write accounts, init KeyPool, set env vars,
│    Proxy        │  write Claude config file
└────────┬────────┘
         ▼
┌─────────────────┐
│ 2. Install      │  gt install + gt rig add
│    Gastown      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 3. Configure    │  gt config agent set kimi-claude claude
│    Agent        │  gt config default-agent kimi-claude
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. Start Dolt   │  Launch SQL server on port 3307
└────────┬────────┘
         ▼
┌─────────────────┐
│ 5. Configure    │  Write ~/.openclaw/openclaw.json
│    OpenClaw     │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 6. Install      │  Copy skills to ~/.openclaw/skills/
│    Skills       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 7. Run Doctor   │  openclaw doctor --repair
└────────┬────────┘
         ▼
┌─────────────────┐
│ 8. Start        │  gt daemon start
│    Daemon       │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 9. Start        │  gt mayor start --agent kimi-claude
│    Mayor        │
└────────┬────────┘
         ▼
┌─────────────────┐
│ 10. Notify      │  Send "Gasclaw is up" via Telegram
└─────────────────┘
```

If any step fails, all previously started services are automatically rolled back.

## Health Monitoring

The monitor loop runs continuously after bootstrap:

```python
while True:
    report = check_health()       # Check all services
    activity = check_activity()   # Check git activity

    if not activity.compliant:
        notify_telegram("ACTIVITY ALERT")

    if any_service_unhealthy:
        notify_telegram("SERVICE DOWN")

    sleep(interval)               # Default: 300 seconds
```

### Health Checks

| Service | Check Method | Healthy When |
|---------|-------------|--------------|
| Dolt | `dolt sql -q "SELECT 1"` | Query succeeds |
| Daemon | `gt daemon status` | Process running |
| Mayor | `gt mayor status` | Process running |
| OpenClaw | `GET http://localhost:18789/health` | HTTP 200 |
| Agents | `gt agents` | Agents listed |

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
2. **Gasclaw**: Orchestrates all actions
3. **OpenClaw**: Makes decisions, communicates via Telegram
4. **Telegram**: Human notifications and commands (native provider)
5. **Gastown**: Executes tasks via Claude Code / Kimi K2.5
6. **Dolt**: Stores all state via beads (`bd` CLI)

## Data Flow

### State Management

All state is stored in Dolt via beads:

```bash
bd create --name "task-123" --content "Fix bug"
bd list
bd search --query "bug"
bd close --name "task-123"
```

### Configuration Locations

| File | Purpose |
|------|---------|
| Environment variables | Runtime config |
| `~/.openclaw/openclaw.json` | OpenClaw config |
| `~/.claude-kimigas/.claude.json` | Claude permission bypass + API key |
| `~/.kimi-accounts/` | API key distribution |
| `/workspace/gt/` | Gastown workspace |

## Security

- API keys never logged or exposed in plaintext
- Key pool state tracked by BLAKE2b hash
- OpenClaw Telegram accepts DMs/groups from all users by default (configurable)
- Auth tokens for gateway API authentication
- Separate key pools prevent cascade failures
- Claude config file handles permission bypass (no `--dangerously-skip-permissions` in process args)
