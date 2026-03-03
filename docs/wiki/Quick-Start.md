# Quick Start

## Prerequisites

1. Installed Gasclaw ([[Installation]])
2. Set all required [[Configuration|environment variables]]

## Start Gasclaw

### Docker

```bash
docker compose up -d
```

### Local

```bash
gasclaw start
```

## Bootstrap Sequence

Gasclaw runs a 10-step startup:

| Step | Action | What Happens |
|------|--------|--------------|
| 1 | Setup Kimi proxy | Init KeyPool, set `ANTHROPIC_BASE_URL`, write Claude config |
| 2 | Install Gastown | `gt install` + `gt rig add` |
| 3 | Configure agent | `gt config agent set kimi-claude claude` |
| 4 | Start Dolt | Launch SQL server |
| 5 | Configure OpenClaw | Write `~/.openclaw/openclaw.json` |
| 6 | Install skills | Copy to `~/.openclaw/skills/` |
| 7 | Run doctor | `openclaw doctor --repair` |
| 8 | Start daemon | `gt daemon start` |
| 9 | Start mayor | `gt mayor start --agent kimi-claude` |
| 10 | Notify | Telegram: "Gasclaw is up" |

If any step fails, previously started services are automatically rolled back.

## Verify

```bash
gasclaw status                          # CLI status
curl http://localhost:18789/health      # OpenClaw health
openclaw logs                           # Gateway logs
```

Send a message to your bot on Telegram — it should respond without requiring @mention.

## Stop

```bash
gasclaw stop          # Local
docker compose down   # Docker
```

## Troubleshooting

- [[Troubleshooting]] — Common issues and fixes
- [[Knowledge Base]] — Lessons learned, Q&A
