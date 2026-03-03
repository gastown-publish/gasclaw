# OpenClaw Gateway — Quick Reference

Source: https://docs.openclaw.ai/gateway/configuration-reference.md

## Config Location

`~/.openclaw/openclaw.json` (JSON5 format — comments and trailing commas allowed)

## Gateway Management

```bash
openclaw gateway start          # Start in background
openclaw gateway run            # Start in foreground (containers)
openclaw gateway stop           # Stop
curl http://localhost:18789/health  # Health check
```

## Validation Commands

```bash
openclaw doctor                          # Health checks + fix suggestions
openclaw doctor --fix                    # Apply recommended repairs
openclaw channels status --probe         # Probe channel credentials
openclaw channels status --probe --json  # Machine-readable probe
```

## Agent Config

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "provider/model" },
      "workspace": "~/.openclaw/workspace"
    },
    "list": [{
      "id": "main",
      "identity": { "name": "Bot Name", "emoji": "🏭" },
      "instructions": "..."
    }]
  }
}
```

## Skills

```
~/.openclaw/skills/<name>/
├── SKILL.md           # YAML frontmatter + description
└── scripts/
    └── script.sh      # Executable
```

Skills auto-install on startup. Scripts must be `chmod +x`.

## Hot Reload

Config changes are detected and hot-reloaded automatically.
Invalid configs are rejected with a log warning — the previous valid config stays active.

## Key Config Sections

| Section | Purpose |
|---------|---------|
| `agents` | Agent list, models, workspace |
| `channels` | Telegram, Discord, WhatsApp, etc. |
| `messages` | ackReaction, groupChat settings |
| `commands` | Slash commands, native commands |
| `gateway` | Port, auth, mode |
| `tools` | Exec security, browser |
| `plugins` | Memory, extensions |
| `env` | Environment variables passed to agents |

## CRITICAL RULES for Config Changes

1. ALWAYS read the official docs for the specific field BEFORE changing it
2. ALWAYS run `openclaw doctor` AFTER any config change
3. ALWAYS run `openclaw channels status --probe` to verify channel health
4. NEVER put group chat IDs in `allowFrom` — that's for DM user IDs only
5. NEVER guess config values — invalid values are silently ignored
6. Test the change end-to-end (send a message, check logs)
