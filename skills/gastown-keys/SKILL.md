---
name: gastown-keys
description: Manage Kimi API key pool - check status, force rotation, handle rate limits
metadata:
  openclaw:
    emoji: 🔑
    os:
      - linux
    requires:
      bins: []
parameters:
  action:
    type: string
    description: Action to perform (status, rotate, cooldown)
    required: true
---

# Gastown Key Manager

As the overseer, you control the Kimi API key pool used by Gastown agents. OpenClaw has its own separate key — never mix them.

## Check Key Status

```bash
bash ~/.openclaw/skills/gastown-keys/scripts/key-status.sh
```

Shows: total keys, available keys, rate-limited keys, cooldown timers.

## Force Key Rotation

```bash
bash ~/.openclaw/skills/gastown-keys/scripts/key-rotate.sh
```

Forces rotation to the next available key. Use when:
- Current key is rate-limited
- You want to spread load across keys
- An agent reports 429 errors

## Key Pool Architecture

- **Gastown keys** (`GASTOWN_KIMI_KEYS`): Used by all Gastown agents (mayor, crew, etc.)
- **OpenClaw key** (`OPENCLAW_KIMI_KEY`): Your own key — separate pool, never shared
- Keys are rotated automatically using LRU (least recently used) algorithm
- Rate-limited keys cool down for 5 minutes before being reused

## When to Rotate

1. Agent logs show 429/rate limit errors → force rotation
2. Key status shows all keys rate-limited → wait for cooldown or add more keys
3. Proactively rotate every 30 minutes to distribute load
