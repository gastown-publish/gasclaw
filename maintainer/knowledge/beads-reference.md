# Beads (bd) — Persistent Memory Reference

## What is Beads
Git-backed issue tracking / memory system. Each agent has its own beads repo
for persistent memory that survives container restarts.

## Setup
```bash
export BD_ROOT=/workspace/beads/<agent-id>
cd $BD_ROOT
```

## Key Commands
```
bd new "title"                # Create a new bead
bd new "title" --body "desc"  # Create with description
bd list                       # List all beads
bd show <id>                  # Show bead details
bd edit <id>                  # Edit a bead
bd close <id>                 # Close/resolve a bead
bd comment <id> "text"        # Add comment to bead
bd search "query"             # Search beads
```

## Usage Patterns

### Log a discovery
```bash
bd new "Gateway crashes when Kimi key expires" --body "Root cause: key pool returns expired key. Fix: check expiry before returning."
```

### Track a recurring issue
```bash
bd new "Dolt restart needed after OOM" --body "Every ~12h Dolt hits memory limit. Need to add memory limit config."
```

### Record a fix
```bash
bd comment <id> "Fixed by adding key expiry check in key_pool.py"
bd close <id>
```

## Per-Agent Beads Locations
| Agent | BD_ROOT |
|-------|---------|
| coordinator | /workspace/beads/coordinator |
| sys-architect | /workspace/beads/sys-architect |
| backend-dev | /workspace/beads/backend-dev |
| db-engineer | /workspace/beads/db-engineer |
| devops | /workspace/beads/devops |
| security-auditor | /workspace/beads/security-auditor |
| test-engineer | /workspace/beads/test-engineer |
| api-docs | /workspace/beads/api-docs |
| code-reviewer | /workspace/beads/code-reviewer |
| doctor | /workspace/beads/doctor |

## Best Practices
- Create a bead for every issue discovered
- Comment on beads when making progress
- Close beads when resolved
- Search beads before investigating — the answer may already be there
- Use descriptive titles for easy searching
