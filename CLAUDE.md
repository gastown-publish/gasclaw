# Gasclaw — Claude Code Contributor Guide

You are a maintainer of the **gasclaw** project: a single-container deployment combining Gastown + OpenClaw + KimiGas.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
make dev
make test    # Must pass before any changes
```

## Project Structure

```
src/gasclaw/
├── cli.py              # Typer CLI: start, stop, status, update
├── config.py           # Env var config (pydantic-free, dataclass)
├── bootstrap.py        # Startup orchestration (10-step sequence)
├── health.py           # Health checks + activity compliance
├── gastown/
│   ├── agent_config.py # Write settings/config.json for gt
│   ├── installer.py    # Kimi account setup + gt install
│   └── lifecycle.py    # Start/stop dolt, daemon, mayor
├── kimigas/
│   ├── key_pool.py     # LRU key rotation with rate-limit cooldown
│   └── proxy.py        # ANTHROPIC_BASE_URL env builder
├── openclaw/
│   ├── installer.py    # Write openclaw.json + Telegram config
│   └── skill_manager.py# Copy skills to ~/.openclaw/skills/
└── updater/
    ├── checker.py      # Check versions of gt, claude, openclaw, dolt
    ├── applier.py      # Run update commands
    └── notifier.py     # POST to OpenClaw gateway
skills/                 # OpenClaw skills (4: health, keys, update, agents)
tests/unit/             # 567 unit tests — all mocked, no API keys needed
tests/integration/      # Integration tests (optional, needs services)
```

## Conventions

- **TDD**: Write test first, then implementation
- **Mocking**: All subprocess/httpx calls mocked in unit tests via `monkeypatch` and `respx`
- **No API keys in tests**: Unit tests never need real keys or running services
- **One concern per PR**: Don't bundle unrelated changes
- **Branch naming**: `fix/`, `feat/`, `test/`, `docs/`, `refactor/`

## Testing

```bash
make test          # Unit tests only — run before every commit
make test-all      # Includes integration tests
make lint          # Ruff linting
```

All 567 unit tests must pass. Never modify a test to make it pass — fix the code.

## Architecture Decisions

- **Separate key pools**: `GASTOWN_KIMI_KEYS` (for agents) and `OPENCLAW_KIMI_KEY` (for overseer) are never shared
- **OpenClaw is the overseer**: It monitors all agents, enforces activity compliance, rotates keys
- **Activity benchmark**: Code must be pushed/PR merged every hour (`ACTIVITY_DEADLINE=3600`)
- **LRU key rotation**: Ported from kimigas — rate-limited keys cool down for 5 minutes
- **Health monitor loop**: Runs in foreground after bootstrap, checks every `MONITOR_INTERVAL` seconds

## Common Tasks

### Adding a new config field
1. Add to `GasclawConfig` dataclass in `config.py`
2. Add env var parsing in `load_config()`
3. Add tests in `tests/unit/test_config.py`

### Adding a new OpenClaw skill
1. Create `skills/<name>/SKILL.md` with YAML frontmatter
2. Add scripts in `skills/<name>/scripts/`
3. Skills auto-install on `gasclaw start`

### Adding a new health check
1. Add check function in `health.py`
2. Add to `check_health()` return
3. Add to `HealthReport` dataclass
4. Add tests in `tests/unit/test_health.py`

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GASTOWN_KIMI_KEYS` | Yes | — | Colon-separated Kimi keys for Gastown |
| `OPENCLAW_KIMI_KEY` | Yes | — | Kimi key for OpenClaw (separate pool) |
| `TELEGRAM_BOT_TOKEN` | Yes | — | Telegram bot token |
| `TELEGRAM_OWNER_ID` | Yes | — | Telegram owner user ID |
| `GT_RIG_URL` | No | `/project` | Git URL or path for rig |
| `GT_AGENT_COUNT` | No | `6` | Number of crew workers |
| `MONITOR_INTERVAL` | No | `300` | Health check interval (seconds) |
| `ACTIVITY_DEADLINE` | No | `3600` | Max seconds between commits |
| `DOLT_PORT` | No | `3307` | Dolt SQL server port |

## PR Checklist

Before creating a PR, verify:
- [ ] `make test` passes (all 567 tests)
- [ ] `make lint` passes
- [ ] New code has corresponding tests
- [ ] Commit message follows `<type>: <description>` format
- [ ] PR description includes summary and test plan
