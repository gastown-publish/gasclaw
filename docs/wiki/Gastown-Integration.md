# Gastown Integration

[Gastown](https://github.com/steveyegge/gastown) is the Go-based multi-agent framework at the core of Gasclaw.

## Components

- **Mayor**: Overseer agent for coordination
- **Crew**: Worker agents executing tasks in parallel
- **Daemon**: Background agent lifecycle manager
- **Deacon, Witness, Refinery**: Supporting services
- **Beads** (`bd`): Git-backed issue tracking

## Installation

```bash
# In Docker (from Dockerfile)
go install github.com/steveyegge/gastown/cmd/gt@latest
go install github.com/steveyegge/beads/cmd/bd@latest

# Do NOT use: pip install gastown (wrong package)
```

## Bootstrap Steps

| Step | Command | Notes |
|------|---------|-------|
| Install | `gt install` | Creates workspace at `/workspace/gt` |
| Add rig | `gt rig add <url>` | Must run with `cwd` set to gt root |
| Set agent | `gt config agent set kimi-claude claude` | Register agent name |
| Set default | `gt config default-agent kimi-claude` | |
| Start daemon | `gt daemon start` | |
| Start mayor | `gt mayor start --agent kimi-claude` | |

## Agent Environment

Every `claude` process spawned by Gastown uses:

```
ANTHROPIC_BASE_URL = https://api.kimi.com/coding/
ANTHROPIC_API_KEY  = <kimi-key-from-pool>
CLAUDE_CONFIG_DIR  = ~/.claude-kimigas
```

Permission bypass via `~/.claude-kimigas/.claude.json` with `bypassPermissionsModeAccepted: true`.

## Key Commands

| Command | Purpose |
|---------|---------|
| `gt agents` | List running agents (NOT `gt status --agents`) |
| `gt daemon status` | Check daemon health |
| `gt mayor status` | Check mayor health |

## Workspace Layout

```
/workspace/gt/
├── settings/config.json  # Agent config
├── beads_hq/             # Mayor's beads
├── daemon.log
└── <rig-name>/           # Projects
```

## Troubleshooting

- `gt rig add` fails silently if not run from gt root directory
- Stop Dolt with `pkill -f "dolt sql-server"` (not `dolt sql-server --stop`)
- Check daemon logs at `/workspace/gt/daemon.log`
