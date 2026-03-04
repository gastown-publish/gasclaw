# Gasclaw

**Gastown + OpenClaw + KimiGas in one container.**

A single-container deployment that runs a [Gastown](https://github.com/steveyegge/gastown) multi-agent workspace, managed by an [OpenClaw](https://github.com/openclaw/openclaw) overseer bot on Telegram. All agents use **Kimi K2.5** as their LLM backend through Claude Code's agentic interface.

## Prerequisites

- **Docker Engine 24+** and **Docker Compose v2** — [Install Docker](https://docs.docker.com/engine/install/)

## Quick Start

```bash
git clone git@github.com:gastown-publish/gasclaw.git && cd gasclaw
cp .env.example .env   # add your keys
docker compose up -d
```

## What's Inside

| Component | Role |
|-----------|------|
| [Gastown](https://github.com/steveyegge/gastown) (`gt`) | Multi-agent workspace — Mayor, Crew, Daemon |
| [OpenClaw](https://github.com/openclaw/openclaw) | Overseer — Telegram bot, monitoring, compliance |
| [KimiGas](https://github.com/gastown-publish/kimigas) | LRU key rotation with rate-limit cooldown |
| [AIS](https://github.com/gastown-publish/ais) | tmux-based AI session manager |
| [Dolt](https://github.com/dolthub/dolt) | Version-controlled SQL for agent state |
| [Beads](https://github.com/steveyegge/beads) (`bd`) | Git-backed issue tracking |



<img width="1140" height="816" alt="Google Chrome 2026-03-03 14 37 52" src="https://github.com/user-attachments/assets/3cb146d6-8ed8-4608-93bd-1edd848935aa" />


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

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GASTOWN_KIMI_KEYS` | Yes | Colon-separated Kimi keys for agents |
| `OPENCLAW_KIMI_KEY` | Yes | Kimi key for overseer (separate pool) |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `TELEGRAM_OWNER_ID` | Yes | Telegram user ID |

Optional: `GT_RIG_URL`, `GT_AGENT_COUNT`, `MONITOR_INTERVAL`, `ACTIVITY_DEADLINE`, `DOLT_PORT`, `LOG_LEVEL` — see [Configuration](https://github.com/gastown-publish/gasclaw/wiki/Configuration).

## Documentation

Full docs are on the **[Wiki](https://github.com/gastown-publish/gasclaw/wiki)**:

- [Architecture](https://github.com/gastown-publish/gasclaw/wiki/Architecture)
- [Configuration](https://github.com/gastown-publish/gasclaw/wiki/Configuration)
- [Gastown Integration](https://github.com/gastown-publish/gasclaw/wiki/Gastown-Integration)
- [Kimi Proxy & Key Rotation](https://github.com/gastown-publish/gasclaw/wiki/Kimi-Proxy)
- [OpenClaw & Telegram](https://github.com/gastown-publish/gasclaw/wiki/OpenClaw-Telegram)
- [Docker Deployment](https://github.com/gastown-publish/gasclaw/wiki/Docker-Deployment)
- [Troubleshooting](https://github.com/gastown-publish/gasclaw/wiki/Troubleshooting)
- [Knowledge Base / FAQ](https://github.com/gastown-publish/gasclaw/wiki/Knowledge-Base)

For AI agents: [`llms.txt`](https://github.com/gastown-publish/gasclaw/blob/main/llms.txt) — machine-readable project reference.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
make dev
make test       # 1021 unit tests — no API keys needed
make lint
```

## Project Structure

```
src/gasclaw/
├── cli.py           # Typer CLI
├── config.py        # Env var config
├── bootstrap.py     # 10-step startup
├── health.py        # Health checks
├── gastown/         # gt CLI integration
├── kimigas/         # Key pool + Kimi proxy
├── openclaw/        # OpenClaw config writer
└── updater/         # Version checks
reference/           # Distilled dependency docs (for agents)
scripts/             # Validation scripts
skills/              # OpenClaw skills
tests/unit/          # 1021 unit tests
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CLAUDE.md](CLAUDE.md).

## License

MIT
