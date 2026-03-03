---
name: gasclaw-status
description: "Full system dashboard for the gasclaw maintainer container"
metadata:
  openclaw:
    emoji: "\U0001F4CA"
    os: ["linux"]
    requires:
      bins: ["gh", "git", "python3"]
parameters:
  section:
    type: string
    description: "Section: all, tests, prs, issues, commits, agent, system"
    required: false
---

# Gasclaw Status Dashboard

Shows live status of the gasclaw maintainer system.

## Usage

```bash
bash ~/.openclaw/skills/gasclaw-status/scripts/status.sh [section]
```

## Sections

- **all** (default): Full dashboard
- **tests**: Unit test count and last result
- **prs**: Open PRs and recent merges
- **issues**: Open issues
- **commits**: Recent commit history
- **agent**: Claude Code maintainer agent status
- **system**: Disk, memory, uptime
