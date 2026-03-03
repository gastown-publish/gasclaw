---
name: gasclaw-logs
description: "View container and process logs"
metadata:
  openclaw:
    emoji: "\U0001F4DD"
    os: ["linux"]
    requires:
      bins: ["tail"]
parameters:
  source:
    type: string
    description: "Log source: startup, claude, gateway, tests, all"
    required: true
  lines:
    type: integer
    description: "Number of lines to show (default: 50)"
    required: false
---

# Gasclaw Logs

View logs from different parts of the system.

## Usage

```bash
bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh startup
bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh claude 100
bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh gateway
bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh tests
bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh all
```

## Log Files

- `/workspace/logs/startup.log` — Container startup output
- `/workspace/logs/claude-code.log` — Claude Code agent output
- `/workspace/logs/openclaw-gateway.log` — OpenClaw gateway log
- `/workspace/logs/test-results.log` — Latest test run output
