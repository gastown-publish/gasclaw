# Gasclaw Documentation

**Single-container deployment combining Gastown + OpenClaw + KimiGas.**

Gasclaw is an autonomous code maintenance system that deploys AI agents to monitor, fix, and improve your codebase. All agents use **Kimi K2.5** as their LLM backend via Claude Code's UI.

## What's Inside

| Component | Purpose | Source |
|-----------|---------|--------|
| **Gastown** | Multi-agent workspace (Mayor, Crew, Daemon) | [steveyegge/gastown](https://github.com/steveyegge/gastown) — Go CLI (`gt`) |
| **OpenClaw** | Overseer bot — monitors agents, Telegram interface | npm: `openclaw` — Node.js |
| **KimiGas** | LRU key rotation with rate-limit cooldown | Built-in Python module |
| **Dolt** | Version-controlled SQL database for agent state | [dolthub/dolt](https://github.com/dolthub/dolt) |
| **Beads** | Git-backed issue tracking used by Gastown | [steveyegge/beads](https://github.com/steveyegge/beads) — Go CLI (`bd`) |

## How It Works

```
┌──────────────── Docker Container ────────────────┐
│  OpenClaw Gateway (Telegram) ← human             │
│  Gastown HQ — Mayor + Crew (Claude Code / Kimi)  │
│  Dolt SQL — agent state    KimiGas — key pools   │
│  /project ← your repo (volume mount)             │
└──────────────────────────────────────────────────┘
```

Agents run `claude` CLI with `ANTHROPIC_BASE_URL` pointed at Kimi's API. Permission bypass is via Claude config file — no `--dangerously-skip-permissions` flag.

## Documentation

### Getting Started
- [[Installation]]
- [[Quick Start]]
- [[Configuration]]

### Guides
- [[Architecture]]
- [[Gastown Integration]]
- [[Kimi Proxy]]
- [[OpenClaw Telegram]]
- [[Docker Deployment]]

### Operations
- [[Troubleshooting]]
- [[Knowledge Base]]

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GASTOWN_KIMI_KEYS` | Yes | — | Colon-separated Kimi keys for agents |
| `OPENCLAW_KIMI_KEY` | Yes | — | Kimi key for OpenClaw (separate pool) |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Telegram bot token from @BotFather |
| `TELEGRAM_OWNER_ID` | Yes | — | Telegram user ID (numeric) |
| `GT_RIG_URL` | No | `/project` | Git URL or path for rig |
| `GT_AGENT_COUNT` | No | `6` | Number of crew workers |
| `MONITOR_INTERVAL` | No | `300` | Health check interval (seconds) |
| `ACTIVITY_DEADLINE` | No | `3600` | Max seconds between commits |
| `DOLT_PORT` | No | `3307` | Dolt SQL server port |
