# Gasclaw

Gastown + OpenClaw + KimiGas in one container. A single-container deployment that runs a full Gastown multi-agent workspace, managed by an OpenClaw overseer bot accessible via Telegram. All agents use Kimi K2.5 as their LLM backend.

## Architecture

```
┌─────────────────────── Docker Container ───────────────────────┐
│                                                                 │
│  OpenClaw Gateway (port 18789) — THE OVERSEER                  │
│    ├── Telegram channel → human                                │
│    ├── Kimi K2.5 (own key pool, separate from Gastown)         │
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
# 1. Clone
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw

# 2. Configure
cp .env.example .env
# Edit .env with your keys

# 3. Run
docker compose up -d

# 4. Chat with your bot on Telegram
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GASTOWN_KIMI_KEYS` | Yes | Colon-separated Kimi API keys for Gastown agents |
| `OPENCLAW_KIMI_KEY` | Yes | Kimi API key for OpenClaw (separate pool) |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `TELEGRAM_OWNER_ID` | Yes | Telegram user ID for allowlist |
| `GT_RIG_URL` | No | Git URL or path (default: `/project`) |
| `GT_AGENT_COUNT` | No | Crew worker count (default: 6) |
| `MONITOR_INTERVAL` | No | Health check interval in seconds (default: 300) |
| `ACTIVITY_DEADLINE` | No | Max seconds between commits (default: 3600) |

**Key separation:** Gastown and OpenClaw keys are completely separate pools. Keys are never shared unless you explicitly put the same key in both `GASTOWN_KIMI_KEYS` and `OPENCLAW_KIMI_KEY`.

## OpenClaw as Overseer

OpenClaw is the boss. It:

- Monitors all agents every 5 minutes
- Enforces activity compliance (push/PR every hour)
- Rotates Gastown keys on rate limits
- Restarts failed agents
- Assesses quality of updates, not just quantity
- Reports to the human via Telegram

## Development

```bash
# Install
python -m venv .venv && source .venv/bin/activate
make dev

# Test
make test          # Unit tests only
make test-all      # Include integration tests

# Lint
make lint
```

## Project Structure

```
src/gasclaw/
├── cli.py              # typer CLI: start, stop, status, update
├── config.py           # Env var config loading
├── bootstrap.py        # Startup orchestration
├── health.py           # Health checks + activity compliance
├── gastown/
│   ├── agent_config.py # Write settings/config.json
│   ├── installer.py    # gt install, kimi accounts
│   └── lifecycle.py    # Start/stop dolt, daemon, mayor
├── kimigas/
│   ├── key_pool.py     # LRU key rotation
│   └── proxy.py        # Claude proxy env builder
├── openclaw/
│   ├── installer.py    # Write openclaw.json
│   └── skill_manager.py# Install skills
└── updater/
    ├── checker.py      # Version checks
    ├── applier.py      # Apply updates
    └── notifier.py     # Telegram notifications
```

## Adding Skills

Create a new directory in `skills/` with:

```
skills/my-skill/
├── SKILL.md           # Skill description (YAML frontmatter + markdown)
└── scripts/
    └── my-script.sh   # Executable scripts
```

Skills are automatically installed to `~/.openclaw/skills/` on startup.
