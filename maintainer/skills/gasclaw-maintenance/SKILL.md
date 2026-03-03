---
name: gasclaw-maintenance
description: "Control the Claude Code maintainer agent"
metadata:
  openclaw:
    emoji: "\U0001F527"
    os: ["linux"]
    requires:
      bins: ["python3"]
parameters:
  action:
    type: string
    description: "Action: status, trigger, pause, resume, frequency, restart"
    required: true
  interval:
    type: integer
    description: "New interval in seconds (for frequency action)"
    required: false
---

# Gasclaw Maintenance Control

Control the Claude Code maintainer agent that autonomously maintains the gasclaw repo.

## Usage

```bash
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh status
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh trigger    # run now
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh pause
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh resume
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh frequency 600
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh restart
```

## State Files

- `/workspace/state/maintenance.json` — last run info, cycle count
- `/workspace/state/paused` — if present, maintenance is paused
- `/workspace/state/trigger-now` — write to trigger immediate run
- `/workspace/state/claude.pid` — Claude Code process PID
