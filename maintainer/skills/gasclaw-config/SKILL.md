---
name: gasclaw-config
description: "View and edit gasclaw maintainer configuration at runtime"
metadata:
  openclaw:
    emoji: "\u2699\uFE0F"
    os: ["linux"]
    requires:
      bins: ["python3"]
parameters:
  action:
    type: string
    description: "Action: view, get, set, reload"
    required: true
  key:
    type: string
    description: "Config key (dot notation, e.g. maintenance.loop_interval)"
    required: false
  value:
    type: string
    description: "New value (for set action)"
    required: false
---

# Gasclaw Config

View and edit runtime configuration without restarting the container.

## Usage

```bash
bash ~/.openclaw/skills/gasclaw-config/scripts/config.sh view
bash ~/.openclaw/skills/gasclaw-config/scripts/config.sh get maintenance.loop_interval
bash ~/.openclaw/skills/gasclaw-config/scripts/config.sh set maintenance.loop_interval 600
```

## Config File

Located at `/workspace/config/gasclaw.yaml` — also editable from the host.

## Available Settings

| Key | Default | Description |
|-----|---------|-------------|
| maintenance.loop_interval | 300 | Seconds between maintenance cycles |
| maintenance.max_pr_size | 200 | Max lines per PR |
| maintenance.auto_merge | true | Auto-merge passing PRs |
| maintenance.repo | gastown-publish/gasclaw | GitHub repo |
| claude.kimi_base_url | https://api.kimi.com/coding/ | Kimi API endpoint |
| openclaw.gateway_port | 18789 | OpenClaw gateway port |
| logging.level | INFO | Log verbosity |
