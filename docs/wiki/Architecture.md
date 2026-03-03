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

[github.com/steveyegge/gastown](https://github.com/steveyegge/gastown) is the Go-based agent framework. Installed via `go install`, it provides the `gt` CLI.

### Agent Command Flow

Every agent process invokes `claude` (Claude Code CLI). The environment is configured so `claude` talks to Kimi K2.5:

```
gt daemon ──► spawns claude process
                 │
                 ├── ANTHROPIC_BASE_URL = https://api.kimi.com/coding/
                 ├── ANTHROPIC_API_KEY  = <kimi-key-from-pool>
                 └── CLAUDE_CONFIG_DIR  = ~/.claude-kimigas
                         │
                         └── .claude.json (bypassPermissionsModeAccepted: true)
```

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

### Skills

| Skill | Purpose |
|-------|---------|
| `gastown-health` | Health check commands |
| `gastown-keys` | Key management commands |
| `gastown-update` | Update commands |
| `gastown-agents` | Agent control commands |

## KimiGas (Key Pool)

LRU rotation with rate-limit cooldown:

```
Available ──► In Use ──► Rate Limited ──► Cooldown (5 min) ──► Available
```

- Keys tracked by BLAKE2b hash, never stored in plaintext
- Separate pools: agents (`GASTOWN_KIMI_KEYS`) vs overseer (`OPENCLAW_KIMI_KEY`)
- Graceful degradation: if all keys rate-limited, returns the key closest to cooldown expiry

## Bootstrap Sequence

The 10-step startup orchestration:

| Step | Action | What Happens |
|------|--------|--------------|
| 1 | Setup Kimi proxy | Init KeyPool, set env vars, write Claude config |
| 2 | Install Gastown | `gt install` + `gt rig add` |
| 3 | Configure agent | `gt config agent set kimi-claude claude` |
| 4 | Start Dolt | Launch SQL server on port 3307 |
| 5 | Configure OpenClaw | Write `~/.openclaw/openclaw.json` |
| 6 | Install skills | Copy skills to `~/.openclaw/skills/` |
| 7 | Run doctor | `openclaw doctor --repair` |
| 8 | Start daemon | `gt daemon start` |
| 9 | Start mayor | `gt mayor start --agent kimi-claude` |
| 10 | Notify | Send "Gasclaw is up" via Telegram |

If any step fails, all previously started services are automatically rolled back.

## Health Monitoring

The monitor loop runs continuously after bootstrap, checking every 300 seconds (configurable):

| Service | Check Method | Healthy When |
|---------|-------------|--------------|
| Dolt | `dolt sql -q "SELECT 1"` | Query succeeds |
| Daemon | `gt daemon status` | Process running |
| Mayor | `gt mayor status` | Process running |
| OpenClaw | `GET http://localhost:18789/health` | HTTP 200 |
| Activity | `git log --since=<deadline>` | Commits exist within deadline |

## Configuration Locations

| File | Purpose |
|------|---------|
| Environment variables | Runtime config |
| `~/.openclaw/openclaw.json` | OpenClaw config |
| `~/.claude-kimigas/.claude.json` | Claude permission bypass + API key |
| `~/.kimi-accounts/` | API key distribution |
| `/workspace/gt/` | Gastown workspace |
