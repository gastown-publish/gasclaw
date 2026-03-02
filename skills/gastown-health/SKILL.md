---
name: gastown-health
description: Check Gastown system health - Dolt, daemon, mayor, agents, key pool, and activity compliance
metadata:
  openclaw:
    emoji: 🏥
    os:
      - linux
    requires:
      bins:
        - gt
        - dolt
parameters:
  depth:
    type: string
    description: Depth of health check (quick or deep)
    required: false
---

# Gastown Health Monitor

As the overseer, use this skill to check the health of the entire Gastown system.

## Quick Status

```bash
bash ~/.openclaw/skills/gastown-health/scripts/gt-status.sh
```

This shows:
- Dolt SQL server status (port 3307)
- gt daemon status
- Mayor session status
- Active agent count and list
- Key pool status (available/rate-limited)

## Deep Health Check

```bash
bash ~/.openclaw/skills/gastown-health/scripts/gt-health.sh
```

This performs:
- Service connectivity tests
- Agent activity compliance check (must have commits within 1 hour)
- Key pool rotation status
- Memory/CPU usage of agent processes

## Overseer Responsibilities

You are the overseer. When health checks show problems:

1. **Service down** → Restart it using gastown-agents skill
2. **Activity non-compliant** → Check which agents are idle, send them work or restart
3. **Keys rate-limited** → Use gastown-keys skill to rotate
4. **Mayor stuck** → Restart mayor with gastown-agents skill

## Monitoring Schedule

Run the quick status check every 5 minutes. Run the deep health check every 15 minutes.
