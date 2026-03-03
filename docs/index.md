# Gasclaw

[![Tests](https://img.shields.io/badge/tests-606%20passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

**Single-container deployment combining Gastown + OpenClaw + KimiGas**

Gasclaw is an autonomous code maintenance system that deploys AI agents to monitor, fix, and improve your codebase. It combines three powerful components:

- **Gastown**: Agent framework for running AI workers
- **OpenClaw**: Overseer that monitors agents and enforces compliance
- **KimiGas**: Key pool management with LRU rotation for rate limiting

## Quick Start

```bash
# Clone the repository
git clone https://github.com/gastown-publish/gasclaw.git
cd gasclaw

# Set up environment
python -m venv .venv
source .venv/bin/activate
make dev

# Configure environment variables
export GASTOWN_KIMI_KEYS="sk-xxx:sk-yyy:sk-zzz"
export OPENCLAW_KIMI_KEY="sk-aaa"
export TELEGRAM_BOT_TOKEN="123:ABC"
export TELEGRAM_OWNER_ID="999999999"

# Start gasclaw
python -m gasclaw
```

## Features

### Autonomous Maintenance
- Monitors open PRs and merges them after tests pass
- Fixes open issues automatically
- Maintains test coverage
- Sends Telegram reports on all actions

### Activity Compliance
- Enforces code activity every hour (`ACTIVITY_DEADLINE=3600`)
- Tracks git commits, pushes, and PRs
- Alerts when no activity detected

### Key Management
- Separate key pools for agents and overseer
- LRU rotation with 5-minute cooldown on rate limits
- Automatic key health monitoring

### Health Monitoring
- Monitors all services: Dolt, daemon, mayor, OpenClaw
- Foreground health check loop
- Telegram notifications on service failures

## Project Structure

```
src/gasclaw/
├── cli.py              # Typer CLI: start, stop, status, update
├── config.py           # Environment variable configuration
├── bootstrap.py        # 13-step startup sequence
├── health.py           # Health checks and activity compliance
├── gastown/            # Gastown integration
│   ├── agent_config.py
│   ├── installer.py
│   └── lifecycle.py
├── kimigas/            # Key pool management
│   ├── key_pool.py
│   └── proxy.py
├── openclaw/           # OpenClaw integration
│   ├── installer.py
│   ├── lifecycle.py
│   └── skill_manager.py
└── updater/            # Version checking and updates
    ├── checker.py
    ├── applier.py
    └── notifier.py
```

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

## Next Steps

- Read the [Installation Guide](getting-started/installation.md)
- Learn about [Configuration](getting-started/configuration.md)
- Understand the [Architecture](architecture.md)
- Check [Troubleshooting](troubleshooting.md) for common issues
