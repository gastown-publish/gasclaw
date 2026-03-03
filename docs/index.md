# Gasclaw Documentation

[![Tests](https://img.shields.io/badge/tests-628%20passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

**Single-container deployment combining Gastown + OpenClaw + KimiGas.**

Gasclaw is an autonomous code maintenance system that deploys AI agents to monitor, fix, and improve your codebase. All agents use **Kimi K2.5** as their LLM backend via Claude Code's UI — no Anthropic API key required.

## What's Inside

| Component | Purpose | Source |
|-----------|---------|--------|
| **Gastown** | Multi-agent workspace (Mayor, Crew, Daemon) | [steveyegge/gastown](https://github.com/steveyegge/gastown) — Go CLI (`gt`) |
| **OpenClaw** | Overseer bot — monitors agents, Telegram interface | npm: `openclaw` — Node.js |
| **KimiGas** | LRU key rotation with rate-limit cooldown | Built-in Python module |
| **Dolt** | Version-controlled SQL database for agent state | [dolthub/dolt](https://github.com/dolthub/dolt) |
| **Beads** | Git-backed issue tracking used by Gastown | [steveyegge/beads](https://github.com/steveyegge/beads) — Go CLI (`bd`) |

## How It Works

Agents run **Claude Code CLI** (`claude`) with `ANTHROPIC_BASE_URL` pointed at Kimi's API endpoint. This gives you Kimi K2.5 as the backend while using Claude Code's agentic interface. Permission bypass is configured via Claude's config file — no `--dangerously-skip-permissions` flag needed.

```
┌─────────────────────── Docker Container ───────────────────────┐
│                                                                 │
│  OpenClaw Gateway (port 18789) — THE OVERSEER                  │
│    ├── Telegram channel (open DM + group policy)               │
│    ├── Kimi K2.5 (own key, separate from Gastown)              │
│    └── Skills: health, keys, update, agents                    │
│                                                                 │
│  Gastown HQ (/workspace/gt)                                    │
│    ├── Mayor (Claude Code via KimiGas)                         │
│    ├── Deacon, Witness, Refinery                               │
│    ├── Crew (6-8 workers)                                      │
│    ├── Dolt SQL (port 3307)                                    │
│    └── Key rotation pool (separate from OpenClaw)              │
│                                                                 │
│  /project ← volume mount from host                             │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw
cp .env.example .env   # Edit with your keys
docker compose up -d
```

## Documentation Map

### Getting Started
- [Installation](getting-started/installation.md) — Prerequisites and setup
- [Quick Start](getting-started/quickstart.md) — Bootstrap walkthrough
- [Configuration](getting-started/configuration.md) — Environment variables and secrets

### Guides
- [Architecture](architecture.md) — System design and component interaction
- [Gastown Integration](guides/gastown-integration.md) — Real Gastown CLI (`gt`) setup
- [Kimi Proxy & Key Rotation](guides/kimi-proxy.md) — KimiGas, Claude env, and key pools
- [OpenClaw & Telegram](guides/openclaw-telegram.md) — Bot config, policies, and channels
- [Docker Deployment](guides/docker-deployment.md) — Container setup, volumes, and networking

### Reference
- [API: Bootstrap](api/bootstrap.md) — `bootstrap()` and `monitor_loop()`
- [API: Config](api/config.md) — `GasclawConfig` dataclass
- [API: Health](api/health.md) — `HealthReport` and checks
- [API: Key Pool](api/key-pool.md) — `KeyPool` LRU rotation
- [API: Maintenance](api/maintenance.md) — PR merging and issue handling

### Operations
- [Troubleshooting](troubleshooting.md) — Common issues and fixes
- [Knowledge Base / FAQ](knowledge-base.md) — Lessons learned, Q&A
- [Migration](api/migration.md) — Migrating from openclaw-launcher

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GASTOWN_KIMI_KEYS` | Yes | — | Colon-separated Kimi keys for Gastown agents |
| `OPENCLAW_KIMI_KEY` | Yes | — | Kimi key for OpenClaw (separate pool) |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Telegram bot token from @BotFather |
| `TELEGRAM_OWNER_ID` | Yes | — | Telegram user ID (numeric) |
| `GT_RIG_URL` | No | `/project` | Git URL or path for rig |
| `GT_AGENT_COUNT` | No | `6` | Number of crew workers |
| `MONITOR_INTERVAL` | No | `300` | Health check interval (seconds) |
| `ACTIVITY_DEADLINE` | No | `3600` | Max seconds between commits |
| `DOLT_PORT` | No | `3307` | Dolt SQL server port |
| `LOG_LEVEL` | No | `INFO` | DEBUG, INFO, WARNING, ERROR |
