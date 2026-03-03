# Gasclaw — AI Agent Documentation

> **Optimized for AI Agents**: This document provides condensed, structured information for AI agents contributing to or working with the gasclaw ecosystem.

---

## Quick Links

| Resource | URL | Purpose |
|----------|-----|---------|
| **Gasclaw Repo** | https://github.com/gastown-publish/gasclaw | Single-container Gastown + OpenClaw + KimiGas |
| **Gas Town (gt)** | https://github.com/steveyegge/gastown | Multi-agent workspace manager |
| **Gas Town Docs** | https://docs.gt.villamarket.ai | Official Gastown documentation |
| **OpenClaw** | https://github.com/gastown-publish/openclaw-launcher | Telegram gateway for AI agents |
| **Kimi CLI** | https://github.com/MoonshotAI/kimi-cli | Kimi Code CLI agent |
| **Kimi Docs** | https://moonshotai.github.io/kimi-cli/en/ | Official Kimi CLI documentation |
| **AIS** | https://github.com/gastown-publish/ais | AI session manager for tmux |
| **KimiGas** | https://github.com/gastown-publish/kimigas | Kimi proxy for Claude Code |
| **Gas Town Monitor** | https://github.com/gastown-publish/gastown-monitor | TUI dashboard for monitoring |
| **N-Skills** | https://github.com/gastown-publish/n-skills | Gas Town custom plugins |
| **Homebrew Tap** | https://github.com/gastown-publish/homebrew-tap | Homebrew formulas |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SINGLE DOCKER CONTAINER                       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  OpenClaw Gateway (port 18789) — THE OVERSEER            │  │
│  │  ├── Telegram channel → human                            │  │
│  │  ├── Kimi K2.5 (separate key pool)                       │  │
│  │  └── Skills: health, keys, update, agents                │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Gastown HQ (/workspace/gt)                              │  │
│  │  ├── Mayor (Claude Code via KimiGas)                     │  │
│  │  ├── Deacon, Witness, Refinery                           │  │
│  │  ├── Crew (6-8 workers)                                  │  │
│  │  ├── Dolt SQL (port 3307)                                │  │
│  │  └── Key rotation pool (separate from OpenClaw)          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  /project ← volume mount from host                       │  │
│  │  (persistent workspace)                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Principle**: Gastown runs **INSIDE** the container, not outside. The entire system is self-contained.

---

## Prerequisites

### System Requirements
- **Docker** 24.0+ with Docker Compose
- **Git** 2.25+
- **4GB RAM** minimum (8GB recommended)
- **10GB disk space**

### API Keys Required

| Variable | Source | Purpose |
|----------|--------|---------|
| `GASTOWN_KIMI_KEYS` | https://platform.kimi.com | Colon-separated keys for Gastown agents |
| `OPENCLAW_KIMI_KEY` | https://platform.kimi.com | Key for OpenClaw overseer |
| `TELEGRAM_BOT_TOKEN` | https://t.me/BotFather | Telegram bot token |
| `TELEGRAM_OWNER_ID` | https://t.me/userinfobot | Your Telegram user ID |

### Optional Tools for Development
- **Go 1.23+** - for Gas Town from source
- **Node.js 22+** - for Claude Code
- **Python 3.12+** - for gasclaw development
- **Dolt 1.82.4+** - SQL database
- **tmux 3.0+** - session management

---

## Quick Start (5 minutes)

```bash
# 1. Clone
git clone https://github.com/gastown-publish/gasclaw.git
cd gasclaw

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Run
docker compose up -d

# 4. Chat with your bot on Telegram
```

---

## Component Reference

### Gasclaw (This Repo)
**Purpose**: Single-container orchestration of Gastown + OpenClaw + KimiGas

**Key Commands**:
```bash
gasclaw start    # Bootstrap all services and monitor
gasclaw stop     # Stop all services
gasclaw status   # Show health status
gasclaw update   # Check and apply updates
```

**Environment Variables**:
```bash
GASTOWN_KIMI_KEYS=sk-xxx:sk-yyy:sk-zzz  # Required: Gastown agent keys
OPENCLAW_KIMI_KEY=sk-aaa                 # Required: OpenClaw overseer key
TELEGRAM_BOT_TOKEN=xxx                   # Required: Bot token
TELEGRAM_OWNER_ID=123456789              # Required: Owner user ID
GT_RIG_URL=/project                      # Optional: Git URL or path
GT_AGENT_COUNT=6                         # Optional: Crew workers
MONITOR_INTERVAL=300                     # Optional: Health check interval (seconds)
ACTIVITY_DEADLINE=3600                   # Optional: Max seconds between commits
```

### Gas Town (gt)
**Purpose**: Multi-agent workspace manager with persistent work tracking

**Installation**:
```bash
# macOS (Homebrew)
brew install gastown

# npm
npm install -g @gastown/gt

# Go
 go install github.com/steveyegge/gastown/cmd/gt@latest
```

**Key Commands**:
```bash
gt install ~/gt --git                    # Initialize workspace
gt rig add myproject https://github.com/you/repo.git  # Add project
gt crew add yourname --rig myproject     # Create crew workspace
gt mayor attach                          # Start Mayor session
gt agents                                # List active agents
gt sling <bead-id> <rig>                 # Assign work to agent
```

**Documentation**: https://docs.gt.villamarket.ai

### OpenClaw
**Purpose**: Telegram gateway for AI agents with skill system

**Key Features**:
- Telegram bot interface for human oversight
- Skill-based agent capabilities
- Health monitoring and notifications
- Key rotation management

**Skills** (in `skills/` directory):
- `gastown-health` — System health checks
- `gastown-keys` — API key rotation
- `gastown-update` — Update management
- `gastown-agents` — Agent lifecycle management

### Kimi CLI
**Purpose**: Kimi Code CLI agent with ACP support

**Installation**:
```bash
pip install kimi-cli
```

**Key Commands**:
```bash
kimi                    # Interactive mode
kimi -c "fix the bug"   # One-shot mode
kimi --yolo             # Auto-approve mode
kimi acp                # ACP server mode
```

**Documentation**: https://moonshotai.github.io/kimi-cli/en/

### AIS (AI Sessions)
**Purpose**: Session manager for Claude Code and Kimi Code in tmux

**Installation**:
```bash
curl -sL https://raw.githubusercontent.com/gastown-publish/ais/main/ais.sh -o ~/.local/bin/ais
chmod +x ~/.local/bin/ais
```

**Key Commands**:
```bash
ais create worker1 -a kimi -A 1 -c "fix the tests"
ais ls                                  # List all sessions
ais inspect worker1 -n 100              # Capture last 100 lines
ais inject worker1 "run the tests"      # Send command
ais kill worker1                        # Graceful shutdown
```

### KimiGas
**Purpose**: Kimi proxy for Claude Code — enables Claude Code to use Kimi K2.5

**Key Features**:
- LRU key rotation with rate-limit cooldown
- Proxy environment builder
- Separate key pool management

**Repository**: https://github.com/gastown-publish/kimigas

---

## Development Setup

```bash
# Clone forked repo
git clone https://github.com/YOUR_USERNAME/gasclaw.git
cd gasclaw

# Python setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
make test          # Unit tests
make test-all      # Include integration tests
make lint          # Ruff linting
```

---

## Testing

**Unit Tests**: 97 tests, all mocked, no API keys needed
```bash
python -m pytest tests/unit -v
```

**Integration Tests**: Require running services
```bash
python -m pytest tests/integration -v
```

**Linting**:
```bash
ruff check src/ tests/
ruff format src/ tests/
```

---

## Project Structure

```
src/gasclaw/
├── cli.py              # Typer CLI: start, stop, status, update
├── config.py           # Env var config (pydantic-free, dataclass)
├── bootstrap.py        # 17-step startup orchestration
├── health.py           # Health checks + activity compliance
├── gastown/
│   ├── agent_config.py # Write settings/config.json
│   ├── installer.py    # Kimi accounts + gt install
│   └── lifecycle.py    # Start/stop dolt, daemon, mayor
├── kimigas/
│   ├── key_pool.py     # LRU key rotation
│   └── proxy.py        # ANTHROPIC_BASE_URL env builder
├── openclaw/
│   ├── installer.py    # Write openclaw.json
│   ├── skill_manager.py# Install skills
│   └── doctor.py       # Config verification
└── updater/
    ├── checker.py      # Version checks
    ├── applier.py      # Apply updates
    └── notifier.py     # Telegram notifications

skills/                 # OpenClaw skills
tests/unit/             # 97 unit tests
tests/integration/      # Integration tests
```

---

## Bootstrap Sequence

1. Load config from env vars
2. Setup Kimi accounts (~/.kimi-accounts/)
3. Write agent config
4. Run `gt install`
5. Run `gt rig add`
6. Start Dolt SQL server (port 3307)
7. Configure OpenClaw (~/.openclaw/)
8. Install skills
9. Run `openclaw doctor`
10. Start `gt daemon`
11. Start Mayor (`gt mayor start --agent kimi-claude`)
12. Send Telegram notification
13. Enter health monitor loop

---

## Key Concepts

### Activity Compliance
Agents must push commits or create PRs every `ACTIVITY_DEADLINE` seconds (default: 3600 = 1 hour). Non-compliance triggers alerts.

### Key Separation
- `GASTOWN_KIMI_KEYS` — for Gastown agents (Mayor, Crew, etc.)
- `OPENCLAW_KIMI_KEY` — for OpenClaw overseer
- Keys are **never shared** unless explicitly configured

### Key Rotation
LRU (Least Recently Used) rotation with 5-minute cooldown for rate-limited keys. State persisted to `~/.kimigas_state.json`.

### Health Monitoring
- Runs every `MONITOR_INTERVAL` seconds (default: 300 = 5 minutes)
- Checks: Dolt, daemon, mayor, agent activity, key pool
- Sends Telegram alerts for issues

---

## Common Tasks

### Add a New Config Field
1. Add to `GasclawConfig` dataclass in `config.py`
2. Add env var parsing in `load_config()`
3. Add tests in `tests/unit/test_config.py`

### Add a New OpenClaw Skill
1. Create `skills/<name>/SKILL.md` with YAML frontmatter
2. Add scripts in `skills/<name>/scripts/`
3. Make scripts executable (`chmod +x`)
4. Skills auto-install on `gasclaw start`

### Add a New Health Check
1. Add check function in `health.py`
2. Add to `check_health()` return
3. Add to `HealthReport` dataclass
4. Add tests in `tests/unit/test_health.py`

---

## Troubleshooting

### Tests Fail
```bash
# Check Python version (need 3.12+)
python --version

# Reinstall dependencies
pip install -e ".[dev]"
```

### Container Won't Start
```bash
# Check logs
docker compose logs -f gasclaw

# Verify env vars
cat .env

# Check port availability
lsof -i :18789
```

### Agent Not Responding
```bash
# Check agent status
gt agents

# Restart mayor
gt mayor stop
gt mayor start --agent kimi-claude

# Check logs
gt logs mayor
```

---

## Contributing

**Workflow**:
1. Branch from latest main: `git checkout main && git pull`
2. Create branch: `git checkout -b fix/<issue-number>-<description>`
3. Write tests first (TDD)
4. Run `make test` before every commit
5. Commit: `git commit -m "fix: description"`
6. Push and create PR
7. Ensure CI passes

**Branch Naming**:
- `fix/` — Bug fixes
- `feat/` — New features
- `test/` — Test additions
- `docs/` — Documentation
- `refactor/` — Code refactoring

---

## External Dependencies

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| Python | 3.12+ | Runtime | python.org |
| Node.js | 22+ | Claude Code | nodesource.com |
| Go | 1.23+ | Gas Town | go.dev |
| Dolt | 1.82.4+ | SQL database | dolthub.com |
| tmux | 3.0+ | Session mgmt | apt/brew |
| Claude Code | latest | AI agent | npm |
| Kimi CLI | latest | AI agent | pip |

---

## License

MIT License — see LICENSE file for details.

---

**For AI Agents**: When contributing to this repo, always:
1. Read `CLAUDE.md` for project conventions
2. Run `make test` before any changes
3. Follow the 17-step bootstrap sequence
4. Maintain separation between Gastown and OpenClaw key pools
5. Keep PRs under 200 lines when possible
