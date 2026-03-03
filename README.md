# Gasclaw

Gastown + OpenClaw + KimiGas in one container. A single-container deployment that runs a full Gastown multi-agent workspace, managed by an OpenClaw overseer bot accessible via Telegram. All agents use Kimi K2.5 as their LLM backend through Claude Code's agentic interface.

**OpenClaw is fully embedded — not a separate install.** The single container includes everything: embedded OpenClaw gateway, Gastown agents ([steveyegge/gastown](https://github.com/steveyegge/gastown)), Dolt SQL server, and KimiGas key management.

## What's Inside

| Component | Purpose | Auto-Configured |
|-----------|---------|-----------------|
| **Gastown** | Multi-agent workspace with Mayor, Crew workers, and services | Yes — installed via `gt` CLI (Go) |
| **OpenClaw (embedded)** | Overseer bot that monitors agents and reports to Telegram | Yes — embedded gateway, auto-generated `openclaw.json` |
| **Dolt** | Version-controlled SQL database for agent memory | Yes — runs on port 3307 |
| **KimiGas** | Key pool management with LRU rotation for rate limiting | Yes — separate pools for Gastown and OpenClaw |
| **Beads** | Git-backed issue tracking for agents | Yes — `bd` CLI from [steveyegge/beads](https://github.com/steveyegge/beads) |

On first startup, the bootstrap sequence automatically:
1. Configures Kimi as the Claude Code backend (`ANTHROPIC_BASE_URL`)
2. Writes Claude config for headless operation (permission bypass via config file)
3. Installs and configures Gastown workspace
4. Configures OpenClaw with Telegram (open DM/group policy, no @mention required)
5. Starts all services with automatic rollback on failure

## Architecture

```
┌─────────────────────── Docker Container ───────────────────────┐
│                                                                 │
│  OpenClaw Gateway (port 18789) — THE OVERSEER (embedded)       │
│    ├── Telegram channel (open DM + group policy)               │
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

## Platform Support

| Platform | Status |
|----------|--------|
| Linux amd64/arm64 | Supported |
| macOS Intel (Docker Desktop) | Supported |
| macOS Apple Silicon (Docker Desktop) | Supported |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GASTOWN_KIMI_KEYS` | Yes | Colon-separated Kimi API keys for Gastown agents |
| `OPENCLAW_KIMI_KEY` | Yes | Kimi API key for OpenClaw (separate pool) |
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `TELEGRAM_OWNER_ID` | Yes | Telegram user ID (numeric) |
| `GT_RIG_URL` | No | Git URL or path (default: `/project`) |
| `GT_AGENT_COUNT` | No | Crew worker count (default: 6) |
| `MONITOR_INTERVAL` | No | Health check interval in seconds (default: 300) |
| `ACTIVITY_DEADLINE` | No | Max seconds between commits (default: 3600) |
| `DOLT_PORT` | No | Dolt SQL server port (default: 3307) |
| `LOG_LEVEL` | No | DEBUG, INFO, WARNING, ERROR (default: INFO) |

**Key separation:** Gastown and OpenClaw keys are completely separate pools. Keys are never shared unless explicitly duplicated.

## Key Management

Gasclaw uses **KimiGas** — an LRU key rotation system with automatic rate-limit recovery.

| Feature | Behavior |
|---------|----------|
| **LRU Rotation** | Least-recently-used key selected first |
| **5-Minute Cooldown** | Rate-limited keys quarantined for 5 minutes |
| **Graceful Degradation** | If all keys rate-limited, returns key closest to cooldown expiry |
| **Privacy** | Keys tracked by BLAKE2b hash, never stored in plaintext |

Minimum 2-3 keys recommended for uninterrupted service.

## How Kimi Integration Works

Claude Code CLI reads `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY` from the environment. Gasclaw sets these to point at Kimi's API. Permission bypass is handled via a Claude config file (`bypassPermissionsModeAccepted: true`) — no `--dangerously-skip-permissions` flag needed (which is rejected under root).

## OpenClaw Telegram

OpenClaw uses its **native Telegram provider** (not polling or wrappers). Default config:
- `dmPolicy: "open"` — accepts all DMs
- `groupPolicy: "open"` — accepts all group messages
- `ackReactionScope: "all"` — responds without requiring @mention

## Development

```bash
python -m venv .venv && source .venv/bin/activate
make dev

make test          # 628 unit tests (no API keys needed)
make test-all      # Include integration tests
make lint          # Ruff linting
```

## Documentation

Full documentation is in the [`docs/`](docs/) directory:

- [Home](docs/index.md) — Overview and documentation map
- [Architecture](docs/architecture.md) — System design
- [Gastown Integration](docs/guides/gastown-integration.md) — Real Gastown CLI setup
- [Kimi Proxy & Key Rotation](docs/guides/kimi-proxy.md) — KimiGas details
- [OpenClaw & Telegram](docs/guides/openclaw-telegram.md) — Bot configuration
- [Docker Deployment](docs/guides/docker-deployment.md) — Container setup
- [Troubleshooting](docs/troubleshooting.md) — Common issues
- [Knowledge Base / FAQ](docs/knowledge-base.md) — Lessons learned

## Project Structure

```
src/gasclaw/
├── cli.py              # Typer CLI: start, stop, status, update
├── config.py           # Env var config (dataclass-based)
├── bootstrap.py        # 10-step startup orchestration
├── health.py           # Health checks + activity compliance
├── gastown/
│   ├── agent_config.py # Write settings/config.json for gt
│   ├── installer.py    # Kimi account setup + gt install
│   └── lifecycle.py    # Start/stop dolt, daemon, mayor
├── kimigas/
│   ├── key_pool.py     # LRU key rotation with rate-limit cooldown
│   └── proxy.py        # ANTHROPIC_BASE_URL env + Claude config writer
├── openclaw/
│   ├── installer.py    # Write openclaw.json + Telegram config
│   └── skill_manager.py# Copy skills to ~/.openclaw/skills/
└── updater/
    ├── checker.py      # Version checks (gt, claude, openclaw, dolt)
    ├── applier.py       # Apply updates
    └── notifier.py     # Telegram notifications
skills/                 # OpenClaw skills (health, keys, update, agents)
tests/unit/             # 628 unit tests — all mocked, no API keys needed
tests/integration/      # Integration tests (needs running services)
```

## Migrating from openclaw-launcher

See the [Migration Guide](docs/migrating-from-openclaw-launcher.md) for details on:
- Port changes (18790 → 18789)
- Key separation (single key → dual pool)
- Session preservation and rollback
