# Migrating from openclaw-launcher to Gasclaw

This guide helps you migrate from [openclaw-launcher](https://github.com/gastown-publish/openclaw-launcher) (the multi-container Docker-based OpenClaw deployment) to **Gasclaw** (the unified single-container deployment).

## What Gasclaw Replaces

The entire openclaw-launcher stack is replaced by a single Gasclaw container:

| openclaw-launcher | Gasclaw equivalent |
|-------------------|-------------------|
| Multi-container setup (normal + privileged + deacon) | Single Docker container |
| `orchestrator.sh` cron job | Built-in bootstrap + health monitor |
| `gateway-watcher.sh` | Built-in service health checks |
| OpenClaw gateway (port 18790) | OpenClaw gateway (port 18789) |
| Shell-based lifecycle management | `gasclaw start/stop/status` CLI |
| Manual log aggregation | Telegram notifications + `gasclaw status` |

## Pre-Migration Checklist

Before migrating, complete these steps to ensure a clean transition:

- [ ] **Stop the old gateway** — Only one service can poll a Telegram bot token at a time
- [ ] **Export conversation history** — Back up `~/.openclaw/agents/` if you need session history
- [ ] **Note your Kimi API keys** — You'll need them for the new config
- [ ] **Record your Telegram bot token** — Same bot, new gateway

### Stopping openclaw-launcher

```bash
# Stop all openclaw-launcher containers
cd /path/to/openclaw-launcher
docker compose down

# Stop the orchestrator cron job
sudo systemctl disable openclaw-orchestrator  # if using systemd
# OR remove from crontab
crontab -e  # remove the orchestrator.sh line

# Verify nothing is using port 18790
lsof -i :18790
```

## Configuration Migration

### Port Change

| Setting | openclaw-launcher | Gasclaw |
|---------|-------------------|---------|
| Gateway port | 18790 | 18789 |

If you have external services pointing to port 18790, update them to 18789 or map the port in `docker-compose.yml`:

```yaml
services:
  gasclaw:
    ports:
      - "18790:18789"  # Map old port to new for compatibility
```

### Key Separation

openclaw-launcher uses a single Kimi API key. Gasclaw separates keys into two pools:

| Variable | Purpose | Recommendation |
|----------|---------|----------------|
| `GASTOWN_KIMI_KEYS` | Gastown agents (Mayor, Crew) | 2-3 keys for rotation |
| `OPENCLAW_KIMI_KEY` | OpenClaw overseer bot | 1 dedicated key |

**Migration**: Copy your existing key to both variables, then add more keys to `GASTOWN_KIMI_KEYS` for rotation:

```bash
# .env file
# Old openclaw-launcher had:
# KIMI_API_KEY=sk-your-key

# Gasclaw uses:
GASTOWN_KIMI_KEYS=sk-your-key  # Add more keys later: sk-key1:sk-key2:sk-key3
OPENCLAW_KIMI_KEY=sk-your-key  # Can be same key initially
```

### Environment Variables

Map your openclaw-launcher config to Gasclaw:

| openclaw-launcher | Gasclaw | Notes |
|-------------------|---------|-------|
| `TELEGRAM_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN` | Same value |
| `TELEGRAM_OWNER_ID` | `TELEGRAM_OWNER_ID` | Same value |
| `KIMI_API_KEY` | `GASTOWN_KIMI_KEYS` | Colon-separated list |
| `KIMI_API_KEY` | `OPENCLAW_KIMI_KEY` | Single key for overseer |
| N/A | `GT_AGENT_COUNT` | Crew workers (default: 6) |
| N/A | `MONITOR_INTERVAL` | Health check interval (default: 300s) |

## Session and Memory Migration

### Option 1: Fresh Start (Recommended)

Gasclaw will create new OpenClaw sessions and Gastown workspace. This is the cleanest approach and recommended unless you have critical ongoing work.

### Option 2: Preserve Sessions

To preserve OpenClaw conversation history:

```bash
# On openclaw-launcher host, export agents directory
tar czf openclaw-backup.tar.gz ~/.openclaw/agents/

# Copy to gasclaw host and extract into the container volume
# Mount as volume in docker-compose.yml:
```

```yaml
services:
  gasclaw:
    volumes:
      - ./openclaw-agents:/root/.openclaw/agents:rw
```

**Note**: Session compatibility is not guaranteed. Gasclaw uses a different OpenClaw configuration format.

## Migration Steps

1. **Backup** (on openclaw-launcher host):
   ```bash
   tar czf ~/openclaw-backup-$(date +%Y%m%d).tar.gz ~/.openclaw/
   ```

2. **Stop openclaw-launcher**:
   ```bash
   docker compose down
   ```

3. **Clone and configure Gasclaw**:
   ```bash
   git clone git@github.com:gastown-publish/gasclaw.git
   cd gasclaw
   cp .env.example .env
   # Edit .env with your keys
   ```

4. **Start Gasclaw**:
   ```bash
   docker compose up -d
   ```

5. **Verify**:
   ```bash
   docker compose logs -f
   gasclaw status  # From inside container or with docker exec
   ```

6. **Test Telegram bot** — Send a message to your bot; it should respond via the Gasclaw gateway

## Troubleshooting Migration Issues

### "Conflict: terminated by other getUpdates" Error

**Cause**: The old openclaw-launcher gateway is still polling the Telegram bot.

**Fix**: Ensure all openclaw-launcher containers are stopped:
```bash
docker ps | grep openclaw
docker stop <container_id>
```

### Port Already in Use

**Cause**: Something is still bound to port 18789 or 3307.

**Fix**: Change ports in `.env`:
```bash
DOLT_PORT=3308  # If 3307 is taken
```

### Missing Kimi Keys

**Cause**: Only set `GASTOWN_KIMI_KEYS` but not `OPENCLAW_KIMI_KEY`.

**Fix**: Both variables are required. They can share the same key initially:
```bash
GASTOWN_KIMI_KEYS=sk-your-key
OPENCLAW_KIMI_KEY=sk-your-key
```

### Services Unhealthy After Migration

**Cause**: Partial state from previous installations.

**Fix**: Clear state directories and restart:
```bash
docker compose down
rm -rf ./.gt-data ./.dolt-data  # If mounted locally
docker compose up -d
```

## Post-Migration

Once migration is complete:

1. **Archive openclaw-launcher**:
   ```bash
   mv /path/to/openclaw-launcher /path/to/openclaw-launcher.archived
   ```

2. **Update firewall rules** if you exposed port 18790 externally

3. **Set up monitoring** — Gasclaw sends health alerts via Telegram

4. **Add more Kimi keys** for better rotation:
   ```bash
   # Update .env
   GASTOWN_KIMI_KEYS=sk-key1:sk-key2:sk-key3
   docker compose up -d
   ```

## Rollback

If you need to rollback to openclaw-launcher:

```bash
# Stop Gasclaw
cd gasclaw
docker compose down

# Restore openclaw-launcher
cd /path/to/openclaw-launcher
docker compose up -d
```

## Getting Help

- Check `gasclaw status` for service health
- View logs: `docker compose logs -f`
- Run health check: `gasclaw health`
- Open an issue: [github.com/gastown-publish/gasclaw/issues](https://github.com/gastown-publish/gasclaw/issues)
