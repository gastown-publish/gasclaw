## Your Skills

You have 5 installed skills — use their scripts for structured operations:

| Skill | Purpose | Script |
|-------|---------|--------|
| `gasclaw-status` | Full dashboard | `bash ~/.openclaw/skills/gasclaw-status/scripts/status.sh [section]` |
| `gasclaw-config` | View/edit config | `bash ~/.openclaw/skills/gasclaw-config/scripts/config.sh <action> [key] [value]` |
| `gasclaw-repo` | Repo management | `bash ~/.openclaw/skills/gasclaw-repo/scripts/repo.sh <action> [args]` |
| `gasclaw-maintenance` | Agent control | `bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh <action>` |
| `gasclaw-logs` | View logs | `bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh <source> [lines]` |

## Quick Commands

```bash
# Status
bash ~/.openclaw/skills/gasclaw-status/scripts/status.sh all
bash ~/.openclaw/skills/gasclaw-status/scripts/status.sh prs

# Config
bash ~/.openclaw/skills/gasclaw-config/scripts/config.sh view
bash ~/.openclaw/skills/gasclaw-config/scripts/config.sh set maintenance.loop_interval 600

# Repo
gh pr list --repo gastown-publish/gasclaw --state open
gh issue list --repo gastown-publish/gasclaw --state open
git -C /workspace/gasclaw log --oneline -10

# Maintenance
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh status
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh trigger
bash ~/.openclaw/skills/gasclaw-maintenance/scripts/maintenance.sh pause

# Logs
bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh claude 50
bash ~/.openclaw/skills/gasclaw-logs/scripts/logs.sh gateway 20
```

## Project Context

- **Repo**: /workspace/gasclaw (Python 3.13, 600+ unit tests)
- **Config**: /workspace/config/gasclaw.yaml (editable from host)
- **Logs**: /workspace/logs/ (startup, claude, gateway, tests)
- **State**: /workspace/state/ (PIDs, maintenance state, pause sentinel)
- **Claude Code** runs as the maintainer agent with full merge authority
- **Tests**: `cd /workspace/gasclaw && source .venv/bin/activate && python -m pytest tests/unit -v`

## Memory

Use beads (`bd` CLI) for ALL persistent memory and state tracking when available. Key bead commands:
- `bd create <type> <title>` — create a new bead
- `bd list` — list all beads
- `bd show <id>` — show bead details
- `bd update <id> <field> <value>` — update a bead
