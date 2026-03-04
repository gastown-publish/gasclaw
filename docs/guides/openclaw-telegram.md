# OpenClaw & Telegram Guide

OpenClaw is the overseer component of Gasclaw. It monitors agents, enforces compliance, and communicates with humans via Telegram. This guide covers how to configure OpenClaw's Telegram integration correctly.

## Architecture

OpenClaw runs **embedded** inside the Gasclaw container — not as a separate installation. The OpenClaw gateway listens on port 18789 and connects to Telegram using its native provider (not polling or a wrapper).

```
Human ◄──► Telegram API ◄──► OpenClaw Gateway (port 18789)
                                    │
                            ┌───────┴───────┐
                            │   Gasclaw     │
                            │   Container   │
                            └───────────────┘
```

## Configuration File

OpenClaw config lives at `~/.openclaw/openclaw.json`. Gasclaw writes this automatically during bootstrap via `write_openclaw_config()` in `src/gasclaw/openclaw/installer.py`.

### Full Telegram Config

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "123456:ABC-DEF...",
      "dmPolicy": "open",
      "allowFrom": ["*"],
      "groupPolicy": "open",
      "streaming": "off"
    }
  },
  "messages": {
    "ackReactionScope": "all"
  }
}
```

### Field Reference

| Field | Type | Values | Purpose |
|-------|------|--------|---------|
| `enabled` | bool | `true` / `false` | Enable/disable Telegram channel |
| `botToken` | string | From @BotFather | Telegram bot authentication |
| `dmPolicy` | string | `"open"`, `"allowlist"`, `"disabled"` | Who can DM the bot |
| `allowFrom` | array | `["*"]` or `["user_id1", ...]` | DM allow list |
| `groupPolicy` | string | `"open"`, `"allowlist"`, `"disabled"` | Who can interact in groups |
| `streaming` | string | `"on"` / `"off"` | Response streaming mode |
| `ackReactionScope` | string | `"all"`, `"none"` | When to auto-react to messages |

### Important Notes

- **`groupPolicy: "owner"`** does NOT exist. Valid values are `"open"`, `"allowlist"`, `"disabled"`. Using an invalid value will be silently ignored.
- When `dmPolicy` is `"open"`, you **must** set `allowFrom: ["*"]` — OpenClaw validates this.
- `ackReactionScope: "all"` makes the bot respond to every message without requiring an @mention.
- `streaming: "off"` is recommended for Telegram to avoid partial message issues.

## Setting Up the Bot

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow prompts
3. Save the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your User ID

Message [@userinfobot](https://t.me/userinfobot) to get your numeric Telegram user ID.

### 3. Get Group Chat ID

For group notifications, the chat ID is negative (e.g., `-1003759869133`). You can get it by:
1. Adding the bot to the group
2. Sending a message in the group
3. Checking `https://api.telegram.org/bot<TOKEN>/getUpdates`

### 4. Configure Environment

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_OWNER_ID="2045995148"
```

## DM vs Group Policies

### Open to Everyone (Recommended for Gasclaw)

```json
{
  "dmPolicy": "open",
  "allowFrom": ["*"],
  "groupPolicy": "open"
}
```

The bot responds to all DMs and all group messages.

### Restricted to Owner

```json
{
  "dmPolicy": "allowlist",
  "allowFrom": ["2045995148"],
  "groupPolicy": "disabled"
}
```

Only the owner can DM; groups are disabled.

### Restricted Groups

```json
{
  "groupPolicy": "allowlist",
  "groupAllowFrom": ["2045995148", "9876543210"]
}
```

Only listed users can interact in groups.

## OpenClaw Agent Configuration

The overseer agent is configured in the same `openclaw.json`:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openrouter/moonshotai/kimi-k2.5",
        "fallbacks": ["openrouter/qwen/qwen3-coder:free"]
      },
      "workspace": "~/.openclaw/workspace"
    },
    "list": [{
      "id": "main",
      "identity": {
        "name": "Gasclaw Overseer",
        "emoji": "🏭"
      },
      "instructions": "You use beads (bd CLI) for ALL memory and state tracking..."
    }]
  }
}
```

OpenClaw uses its **own Kimi key** (`OPENCLAW_KIMI_KEY`), separate from the Gastown agent pool.

## Skills

Skills extend the bot's capabilities. Gasclaw ships with five built-in skills:

| Skill | Directory | Purpose |
|-------|-----------|---------|
| `gastown-health` | `skills/gastown-health/` | Health check commands |
| `gastown-keys` | `skills/gastown-keys/` | Key pool management |
| `gastown-update` | `skills/gastown-update/` | Version update commands |
| `gastown-agents` | `skills/gastown-agents/` | Agent control commands |
| `ais-orchestrator` | `skills/ais-orchestrator/` | Multi-agent tmux orchestration |

Skills are installed to `~/.openclaw/skills/` during bootstrap.

### Adding a Custom Skill

```
skills/my-skill/
├── SKILL.md           # YAML frontmatter + description
└── scripts/
    └── my-script.sh   # Executable script
```

Scripts must be executable (`chmod +x`).

## Gateway Management

### Start the Gateway

```bash
openclaw gateway start       # Background
openclaw gateway run         # Foreground (used in containers)
```

### Stop the Gateway

```bash
openclaw gateway stop
```

### Check Health

```bash
curl http://localhost:18789/health
```

### View Logs

```bash
openclaw logs
# Or in the container:
tail -f /workspace/logs/openclaw-gateway.log
```

## Troubleshooting

### Bot is online but doesn't respond

1. Check gateway: `curl http://localhost:18789/health`
2. Check policies: `cat ~/.openclaw/openclaw.json | python3 -m json.tool`
3. Verify `dmPolicy: "open"` and `ackReactionScope: "all"`
4. Check logs: `openclaw logs` or `tail /workspace/logs/openclaw-gateway.log`

### Bot requires @mention in groups

Set `messages.ackReactionScope` to `"all"`:

```bash
openclaw config set messages.ackReactionScope all
```

Or in `openclaw.json`:
```json
{
  "messages": { "ackReactionScope": "all" }
}
```

### Config changes don't persist after restart

The entrypoint script overwrites `openclaw.json` on every container start. Edit:
- `src/gasclaw/openclaw/installer.py` (Python module)
- `maintainer/entrypoint.sh` step 9 (Docker container)

Both must stay in sync. Runtime changes via `openclaw config set` will be lost on next restart.

### "Provider not found" errors

Ensure the models config is written correctly at `~/.openclaw/agents/main/agent/models.json`. The maintainer entrypoint creates this automatically.

### Gateway fails to start

- Check port 18789 is available: `lsof -i :18789`
- Check for existing gateway: `pgrep -f "openclaw gateway"`
- Kill stale process: `pkill -f "openclaw gateway"`
- Check logs: `cat /workspace/logs/openclaw-gateway.log`
