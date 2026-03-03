# Docker Deployment Guide

Gasclaw runs as a single Docker container with all components pre-installed. This guide covers building, configuring, and running the container.

## Container Contents

The Docker image includes everything:

| Component | Installation | Binary |
|-----------|-------------|--------|
| Python 3.13 | Base image | `python3` |
| Node.js 22 | apt (nodesource) | `node`, `npm` |
| Go 1.24 | Downloaded tarball | `go` |
| Dolt | GitHub release | `dolt` |
| Claude Code | `npm install -g @anthropic-ai/claude-code` | `claude` |
| OpenClaw | `npm install -g openclaw` | `openclaw` |
| KimiGas | `pip install kimi-cli` | — |
| Gastown | `go install github.com/steveyegge/gastown/cmd/gt@latest` | `gt` |
| Beads | `go install github.com/steveyegge/beads/cmd/bd@latest` | `bd` |
| Gasclaw | `pip install .` (from source) | `gasclaw` |

## Quick Start

```bash
# Clone
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw

# Configure
cp .env.example .env
# Edit .env with your keys

# Build and run
docker compose up -d
```

## Environment Variables

Create a `.env` file:

```bash
# Required
GASTOWN_KIMI_KEYS="sk-key1:sk-key2:sk-key3"
OPENCLAW_KIMI_KEY="sk-overseer-key"
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_OWNER_ID="2045995148"

# Optional
GT_RIG_URL="/project"
GT_AGENT_COUNT=6
MONITOR_INTERVAL=300
ACTIVITY_DEADLINE=3600
DOLT_PORT=3307
LOG_LEVEL=INFO
```

## Platform Support

The Docker image is multi-platform:

| Platform | Architecture | Status |
|----------|-------------|--------|
| Linux amd64 | x86_64 | Supported |
| Linux arm64 | ARM64 | Supported |
| macOS Intel | amd64 (Docker Desktop) | Supported |
| macOS Apple Silicon | arm64 (Docker Desktop) | Supported |

```bash
# Build for current platform
docker compose build

# Build for specific platform
docker buildx build --platform linux/amd64,linux/arm64 -t gasclaw .
```

## Volume Mounts

| Mount Point | Purpose | Persistence |
|-------------|---------|-------------|
| `/project` | Host project repository | Required — this is what agents work on |
| `/workspace` | Agent workspace, logs, state | Recommended — preserves state across restarts |

```yaml
# docker-compose.yml
volumes:
  - ./my-project:/project
  - gasclaw-workspace:/workspace
```

## Exposed Ports

| Port | Service | Purpose |
|------|---------|---------|
| 18789 | OpenClaw Gateway | Health checks, API |
| 3307 | Dolt SQL | Internal (no need to expose unless debugging) |

## Maintainer Container

The `maintainer/` directory contains a specialized entrypoint for the Gasclaw Maintainer — a self-maintaining instance that monitors its own repository.

### Entrypoint Flow

The `maintainer/entrypoint.sh` runs a 17-step sequence:

| Step | Action |
|------|--------|
| 1 | Init directories and default config |
| 2 | Load config from `gasclaw.yaml` |
| 3 | Auth (GitHub token, Kimi key, Telegram token) |
| 4 | Set Kimi as Claude backend (`ANTHROPIC_BASE_URL`) |
| 5 | Setup Gastown workspace (`/workspace/gt`) |
| 6 | Write Claude config (permission bypass) |
| 7 | Telegram notification helper function |
| 8 | Run `openclaw doctor` |
| 9 | Write OpenClaw config (Telegram policies, models) |
| 10 | Install OpenClaw skills |
| 11 | Clone/update gasclaw repo |
| 12 | Dev environment setup (venv, pip install) |
| 13 | Run tests |
| 14 | Start OpenClaw gateway |
| 15 | Send startup notification |
| 16 | Setup graceful shutdown handler |
| 17 | Enter maintenance loop (Claude Code cycles) |

### Maintenance Loop

The maintenance loop runs `claude` in prompt mode to:
1. Check and merge open PRs
2. Fix open issues
3. Improve test coverage
4. Report via Telegram after each cycle

### Hot-Reload Config

The loop re-reads `gasclaw.yaml` on each cycle, syncing Telegram allowlists into `openclaw.json`. This allows changing config without restarting the container.

## Common Issues

### Container crash loop

**Cause:** Usually a file permission error. Since `entrypoint.sh` uses `set -euo pipefail`, any command failure terminates the container.

**Diagnosis:**
```bash
docker logs <container_id> --tail 50
```

**Common fix:**
```bash
docker exec -u root <container_id> chown -R 1000:1000 /workspace/
```

### UID mismatch on volumes

Docker bind mounts preserve host UIDs. If the host directory is owned by a different user than the container's `maintainer` (UID 1000), file operations fail.

**Fix:**
```bash
# On the host
sudo chown -R 1000:1000 ./workspace-data/

# Or inside the container as root
docker exec -u root <container_id> chown -R 1000:1000 /workspace/
```

### OpenClaw config overwritten on restart

The entrypoint rewrites `openclaw.json` every time. Manual changes via `openclaw config set` will be lost.

**To make permanent changes:**
1. Edit `maintainer/entrypoint.sh` step 9 (the Python block)
2. Also update `src/gasclaw/openclaw/installer.py` for consistency

### Dolt port conflict

If port 3307 is already in use:
```bash
# Check what's using the port
docker exec <container_id> lsof -i :3307

# Or change the port
export DOLT_PORT=3308
```

### Gateway won't start

```bash
# Check logs
docker exec <container_id> cat /workspace/logs/openclaw-gateway.log

# Check port availability
docker exec <container_id> lsof -i :18789
```

## Building the Image

```bash
# Standard build
docker build -t gasclaw .

# Multi-platform build
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 -t gasclaw:latest --push .
```

## Health Checks

Add to `docker-compose.yml`:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:18789/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```
