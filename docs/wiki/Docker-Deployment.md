# Docker Deployment

Gasclaw runs as a single container with all components pre-installed.

## Quick Start

```bash
git clone git@github.com:gastown-publish/gasclaw.git && cd gasclaw
cp .env.example .env    # Add your keys
docker compose up -d
```

## Container Contents

| Component | Binary |
|-----------|--------|
| Python 3.13 | `python3` |
| Node.js 22 | `node`, `npm` |
| Go 1.24 | `go` |
| Dolt | `dolt` |
| Claude Code | `claude` |
| OpenClaw | `openclaw` |
| Gastown | `gt` |
| Beads | `bd` |
| Gasclaw | `gasclaw` |

## Volumes

| Mount | Purpose |
|-------|---------|
| `/project` | Host project repo (what agents work on) |
| `/workspace` | Agent workspace, logs, state |

## Ports

| Port | Service |
|------|---------|
| 18789 | OpenClaw Gateway |
| 3307 | Dolt SQL (internal) |

## Common Issues

### Container crash loop
Usually file permission errors. Since `entrypoint.sh` uses `set -euo pipefail`, any failure kills the container.

```bash
docker logs <container_id> --tail 50
docker exec -u root <container_id> chown -R 1000:1000 /workspace/
```

### UID mismatch on volumes
Docker bind mounts preserve host UIDs. Fix:
```bash
docker exec -u root <container_id> chown -R 1000:1000 /workspace/
```

### Config overwritten on restart
`entrypoint.sh` rewrites `openclaw.json` every start. Edit source files for permanent changes:
- `src/gasclaw/openclaw/installer.py`
- `maintainer/entrypoint.sh` step 9

### Dolt port conflict
```bash
docker exec <container_id> lsof -i :3307
export DOLT_PORT=3308
```
