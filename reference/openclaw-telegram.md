# OpenClaw Telegram — Quick Reference

Source: https://docs.openclaw.ai/channels/telegram.md

## Config Location

`~/.openclaw/openclaw.json` under `channels.telegram`

## DM Access (channels.telegram)

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| `dmPolicy` | string | `pairing` (default), `allowlist`, `open`, `disabled` | |
| `allowFrom` | array | Numeric user IDs or `["*"]` | DM user IDs ONLY — never group IDs. `open` requires `["*"]` |

## Group Access (channels.telegram) — SEPARATE from DM

| Field | Type | Values | Notes |
|-------|------|--------|-------|
| `groupPolicy` | string | `open`, `allowlist` (default), `disabled` | Valid values ONLY — `"owner"` does NOT exist |
| `groupAllowFrom` | array | Numeric user IDs | Group SENDER filtering — user IDs only, never group chat IDs |
| `groups` | object | Group IDs or `"*"` as keys | Per-group config including `requireMention` |

## Groups Config (channels.telegram.groups)

Controls which groups are allowed AND per-group behavior:

```json
{
  "channels": {
    "telegram": {
      "groups": {
        "*": { "requireMention": false },
        "-1001234567890": {
          "requireMention": false,
          "groupPolicy": "open",
          "allowFrom": ["2045995148"],
          "systemPrompt": "Keep answers brief.",
          "topics": {
            "99": {
              "requireMention": false,
              "skills": ["search"]
            }
          }
        }
      }
    }
  }
}
```

Per-group fields: `requireMention`, `groupPolicy`, `allowFrom`, `skills`, `systemPrompt`, `enabled`, `topics`

## Mention Gating

- **Default: groups REQUIRE @mention** to trigger a reply
- Set `groups.*.requireMention: false` to reply to all messages
- `ackReactionScope` only controls the emoji reaction, NOT whether the bot replies
- `/activation always` toggles per-session (not persistent)

## Telegram Privacy Mode

- Bots default to Privacy Mode — they CANNOT see group messages unless @mentioned
- Fix: BotFather `/setprivacy` → Disable, OR make bot a group admin
- After changing privacy, remove + re-add bot to each group

## Streaming

`channels.telegram.streaming`: `off | partial | block | progress` (default: `partial`)

## Validation Commands

```bash
openclaw doctor                          # Full health check
openclaw channels status --probe         # Probe bot credentials + group config
openclaw channels status --probe --json  # Machine-readable output
```

Key probe fields:
- `canReadAllGroupMessages`: true if privacy mode disabled or bot is admin
- `allowUnmentionedGroups`: true if `requireMention: false` somewhere

## Common Mistakes

1. Putting group chat IDs (negative numbers) in `allowFrom` — that's for DM user IDs only
2. Using `groupPolicy: "owner"` — not a valid value, silently ignored
3. Setting `ackReactionScope: "all"` thinking it makes the bot reply — it only controls reactions
4. Missing `groups.*.requireMention: false` — bot silently skips group messages
5. Not disabling Telegram Privacy Mode — bot can't see group messages
