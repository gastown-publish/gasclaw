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

## Platform Support

Gasclaw runs on Linux and macOS (including Apple Silicon) via Docker:

- **Linux (amd64/arm64)**: Native Docker support
- **macOS Intel (amd64)**: Docker Desktop
- **macOS Apple Silicon (arm64)**: Docker Desktop with native ARM64 support

The Docker image is multi-platform and automatically selects the correct architecture:

```bash
# Build for your current platform
docker compose up -d

# Build for specific platform
docker compose build --build-arg TARGETARCH=arm64
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
| `DOLT_PORT` | No | Dolt SQL server port (default: 3307) |
| `LOG_LEVEL` | No | Log level: DEBUG, INFO, WARNING, ERROR (default: INFO) |

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
make test          # Unit tests only (585 tests)
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

## Troubleshooting

### Bootstrap fails with "dolt process exited early"

**Cause:** Dolt SQL server failed to start, often due to port conflicts or data directory issues.

**Solutions:**
- Check if port 3307 is already in use: `lsof -i :3307`
- Clear Dolt data directory: `rm -rf /workspace/gt/.dolt-data`
- Check Dolt logs for specific errors

### "not a git repository" error in health checks

**Cause:** The `project_dir` path doesn't exist or isn't a git repository.

**Solutions:**
- Verify `PROJECT_DIR` environment variable points to an existing directory
- Ensure the directory contains a `.git` subdirectory
- Run `git init` if needed to initialize a git repository

### Keys exhausted / rate limit errors

**Cause:** All Kimi API keys in the pool are rate-limited.

**Solutions:**
- Wait 5 minutes for rate-limited keys to cool down
- Add more keys to `GASTOWN_KIMI_KEYS`
- Check Kimi dashboard for usage limits

### "Activity compliance" alerts

**Cause:** No git commits or PRs within `ACTIVITY_DEADLINE` seconds (default 1 hour).

**Solutions:**
- Ensure agents are running: check `gt status`
- Verify `project_dir` is correct and is a git repo
- Check agent logs for errors
- Consider increasing `ACTIVITY_DEADLINE` for low-activity periods

### Services show as "unhealthy"

**Cause:** One or more services (dolt, daemon, mayor) are not responding.

**Solutions:**
- Check service status: `gasclaw status`
- View service logs: `gt daemon logs`, `gt mayor logs`
- Restart services: `gasclaw stop && gasclaw start`
- Check system resources (memory, disk space)

### Bootstrap rollback messages

If you see "Bootstrap failed: ... Rolling back...", the bootstrap sequence encountered an error and attempted to clean up partial state. Check the specific error message and:

- Review environment variables are set correctly
- Ensure all binaries (`gt`, `dolt`, `openclaw`) are in PATH
- Check for port conflicts (3307 for Dolt, 18789 for OpenClaw gateway)
- Verify network connectivity for external API calls

### Telegram bot not responding

**Cause:** Bot token invalid, network issues, or OpenClaw gateway not running.

**Solutions:**
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check `TELEGRAM_OWNER_ID` matches your Telegram user ID
- Ensure OpenClaw gateway is running: `curl http://localhost:18789/health`
- Check firewall rules allow outbound connections to Telegram API
