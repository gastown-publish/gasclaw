# Gastown (`gt`) CLI — Quick Reference

Source: https://github.com/steveyegge/gastown

## Installation

```bash
go install github.com/steveyegge/gastown/cmd/gt@latest
```

## Workspace Setup

```bash
gt install                        # Initialize workspace at current directory
gt rig add <url>                  # Register a project repo (must run from gt root)
gt config agent set <name> <cmd>  # Register a named agent (e.g., "kimi-claude" "claude")
gt config default-agent <name>    # Set the default agent
```

## Service Management

```bash
# Daemon (agent lifecycle manager)
gt daemon start
gt daemon stop
gt daemon status

# Mayor (overseer agent)
gt mayor start --agent <name>
gt mayor stop
gt mayor status

# Agents
gt agents                         # List running agents (NOT gt status --agents)
```

## Key Commands

| Command | Purpose |
|---------|---------|
| `gt install` | Initialize workspace |
| `gt rig add <url>` | Register project (run from gt root with `cwd`) |
| `gt config agent set <n> <cmd>` | Register agent |
| `gt config default-agent <n>` | Set default agent |
| `gt daemon start/stop/status` | Daemon lifecycle |
| `gt mayor start --agent <n>` | Start mayor |
| `gt agents` | List agents |

## Important Notes

- `gt rig add` MUST be run with `cwd` set to the gt workspace directory
- Use `gt agents` to list agents — NOT `gt status --agents` (wrong flag)
- Dolt stop: use `pkill -f "dolt sql-server"` (not `dolt sql-server --stop` — unreliable in containers)
- Agent command is plain `claude` — permission bypass handled by Claude config file

## Workspace Layout

```
/workspace/gt/
├── .git/
├── .dolt-data/           # Dolt SQL database
├── settings/config.json  # Agent configuration
├── beads_hq/             # Mayor's bead workspace
├── daemon.log
└── <rig-name>/           # Registered projects
```
