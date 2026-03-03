# OpenClaw & Telegram

OpenClaw is the overseer component. It communicates via Telegram using its native provider.

## Correct Config

`~/.openclaw/openclaw.json`:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "YOUR_TOKEN",
      "dmPolicy": "open",
      "allowFrom": ["*"],
      "groupPolicy": "open",
      "groups": { "*": { "requireMention": false } },
      "streaming": "off"
    }
  },
  "messages": {
    "ackReactionScope": "all"
  }
}
```

## Field Reference

| Field | Values | Notes |
|-------|--------|-------|
| `dmPolicy` | `open`, `allowlist`, `disabled` | Who can DM the bot |
| `allowFrom` | `["*"]` or user IDs | DM allow list. `open` requires `["*"]` |
| `groupPolicy` | `open`, `allowlist`, `disabled` | Group access. `"owner"` does NOT exist |
| `groups.*.requireMention` | `true`/`false` | Default `true` — must set `false` for auto-reply |
| `ackReactionScope` | `all`, `none` | Controls emoji reaction only, NOT replies |
| `streaming` | `on`/`off` | `off` recommended for Telegram |

## Critical Notes

- `ackReactionScope` only controls the emoji reaction, NOT whether the bot replies
- `groups.*.requireMention: false` is what actually makes the bot reply without @mention
- `groupPolicy: "owner"` does NOT exist and is silently ignored
- When `dmPolicy: "open"`, OpenClaw requires `allowFrom: ["*"]`
- Config is overwritten by `entrypoint.sh` on container restart — edit source files for permanent changes

## Telegram Privacy Mode

Bots default to Privacy Mode — they cannot see group messages unless @mentioned. Fix:
1. BotFather → `/setprivacy` → Disable, OR
2. Make bot a group admin
3. After changing, remove and re-add bot to each group

## Skills

| Skill | Purpose |
|-------|---------|
| `gastown-health` | Health check commands |
| `gastown-keys` | Key pool management |
| `gastown-update` | Update management |
| `gastown-agents` | Agent control |

## Gateway Commands

```bash
openclaw gateway start        # Background
openclaw gateway run          # Foreground (containers)
openclaw gateway stop
curl http://localhost:18789/health
openclaw logs
openclaw doctor --repair
openclaw channels status --probe
```
