# Quick Start

This guide will get you up and running with Gasclaw in minutes.

## Prerequisites

1. Installed Gasclaw (`make dev` or Docker)
2. Set all [required environment variables](configuration.md)
3. Verified installation with `make test`

## Start Gasclaw

### Docker (Production)

```bash
docker compose up -d
```

### Local

```bash
python -m gasclaw
# Or:
gasclaw start
```

## Bootstrap Sequence

When you start Gasclaw, it runs a 10-step sequence:

| Step | Action | What Happens |
|------|--------|--------------|
| 1 | Setup Kimi proxy | Init KeyPool, set `ANTHROPIC_BASE_URL`, write Claude config |
| 2 | Install Gastown | `gt install` + `gt rig add` |
| 3 | Configure agent | `gt config agent set kimi-claude claude` |
| 4 | Start Dolt | Launch SQL server on configured port |
| 5 | Configure OpenClaw | Write `~/.openclaw/openclaw.json` |
| 6 | Install skills | Copy skills to `~/.openclaw/skills/` |
| 7 | Run doctor | `openclaw doctor --repair` |
| 8 | Start daemon | `gt daemon start` |
| 9 | Start mayor | `gt mayor start --agent kimi-claude` |
| 10 | Notify | Send "Gasclaw is up" via Telegram |

Example output:

```
INFO  Configuring Kimi proxy for Claude Code (3 keys)
INFO  ANTHROPIC_BASE_URL set to Kimi backend (key via pool)
INFO  Installing Gastown with rig_url=/project
INFO  Configuring Gastown agent
INFO  Starting Dolt
INFO  Dolt started successfully
INFO  Configuring OpenClaw in /root/.openclaw
INFO  Installing skills
INFO  Running openclaw doctor
INFO  Openclaw doctor check passed
INFO  Starting gt daemon
INFO  Starting mayor agent
INFO  All services started successfully
INFO  Sending startup notification
INFO  Starting monitor loop with interval=300 seconds
```

If any step fails, previously started services are automatically rolled back.

## Verify It's Working

### Check Status

```bash
gasclaw status
```

### Test Telegram

Send a message to your bot on Telegram. With the default config (`dmPolicy: "open"`, `ackReactionScope: "all"`), it should respond to any message without requiring @mention.

### Health Endpoint

```bash
curl http://localhost:18789/health
```

### Check Logs

```bash
openclaw logs
# Or in containers:
tail -f /workspace/logs/openclaw-gateway.log
```

## Stop Gasclaw

Press `Ctrl+C` to stop the monitor loop, or:

```bash
gasclaw stop
```

In Docker:

```bash
docker compose down
```

## What Happens Next

Once running, Gasclaw will:

1. **Monitor health** — Check all services every 5 minutes
2. **Enforce activity** — Alert if no commits within 1 hour
3. **Rotate keys** — Automatically handle Kimi rate limits
4. **Report via Telegram** — Notifications for all events

## Troubleshooting

If something goes wrong:

1. Check logs: `openclaw logs`
2. Verify env vars: `env | grep -E 'KIMI|TELEGRAM|ANTHROPIC'`
3. Run doctor: `openclaw doctor --repair`
4. Check gateway: `curl http://localhost:18789/health`
5. See [Troubleshooting](../troubleshooting.md) for common issues
6. See [Knowledge Base](../knowledge-base.md) for documented solutions
