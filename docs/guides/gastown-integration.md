# Gastown Integration Guide

Gastown is the multi-agent orchestration framework at the core of Gasclaw. This guide covers how the real Gastown (`gt` CLI) is installed, configured, and managed.

## What Is Gastown?

Gastown ([github.com/steveyegge/gastown](https://github.com/steveyegge/gastown)) is a Go-based system for running multiple AI agents in a shared workspace. It consists of:

- **Mayor**: The overseer agent that coordinates work
- **Crew**: Worker agents that execute tasks
- **Daemon**: Background process managing agent lifecycle
- **Deacon, Witness, Refinery**: Supporting services for observation, state management
- **Beads (`bd`)**: Git-backed issue tracking ([github.com/steveyegge/beads](https://github.com/steveyegge/beads))

All agent processes invoke the `claude` CLI, which Gasclaw redirects to Kimi K2.5 via environment variables.

## Installation

### In Docker (Production)

The Dockerfile installs Gastown from source using Go:

```dockerfile
# Go 1.25 (multi-platform)
RUN curl -fsSL https://go.dev/dl/go1.25.7.linux-${TARGETARCH}.tar.gz | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"

# Gastown (gt) — real Go CLI
RUN go install github.com/steveyegge/gastown/cmd/gt@latest

# Beads (bd) — git-backed issue tracking
RUN go install github.com/steveyegge/beads/cmd/bd@latest
```

Do **not** use `pip install gastown` — that is a different, incorrect package.

### Local Development

```bash
# Install Go 1.25+
go install github.com/steveyegge/gastown/cmd/gt@latest
go install github.com/steveyegge/beads/cmd/bd@latest

# Verify
gt --help
bd --help
```

## Bootstrap Integration

Gasclaw's bootstrap sequence (in `src/gasclaw/bootstrap.py`) configures Gastown in steps 2-3:

### Step 2: Install Gastown

```python
gastown_install(gt_root=gt_root, rig_url=config.gt_rig_url)
```

This runs:
1. `gt install` — Initializes the Gastown workspace at `/workspace/gt`
2. `gt rig add <rig_url>` — Registers the project repository (default: `/project`)

The `gt rig add` command **must** be run with `cwd` set to the `gt_root` directory, otherwise it creates the rig in the wrong location.

### Step 3: Configure Agent

```python
configure_agent(agent_name="kimi-claude", agent_command="claude")
```

This runs:
1. `gt config agent set kimi-claude claude` — Registers the agent
2. `gt config default-agent kimi-claude` — Sets it as default

The command is just `claude` (not `claude --dangerously-skip-permissions`). Permission bypass is handled by the Claude config file, and the Kimi backend is handled by `ANTHROPIC_BASE_URL`.

## Workspace Layout

After bootstrap, the Gastown workspace looks like:

```
/workspace/gt/
├── .git/                    # Git repository
├── .dolt-data/              # Dolt SQL database
├── settings/
│   └── config.json          # Agent configuration
├── beads_hq/                # Mayor's bead workspace
├── beads_deacon/            # Deacon's bead workspace
├── daemon.log               # Daemon process log
└── <rig-name>/              # Registered project(s)
```

## Service Management

### Starting Services

Services are started in order by `bootstrap.py`:

```python
start_dolt()              # Dolt SQL server (port 3307)
start_daemon()            # gt daemon (agent lifecycle manager)
start_mayor(agent="kimi-claude")  # Mayor agent
```

### Stopping Services

The `stop_all()` function in `gastown/lifecycle.py` stops everything:

```python
stop_all()  # Stops mayor, daemon, and dolt
```

Dolt is stopped using `pkill -f "dolt sql-server"` (not `dolt sql-server --stop`, which is unreliable in containers).

### Health Checks

| Service | Check | Command |
|---------|-------|---------|
| Dolt | SQL query | `dolt sql -q "SELECT 1"` |
| Daemon | Process status | `gt daemon status` |
| Mayor | Process status | `gt mayor status` |
| Agents | List running | `gt agents` |

Note: Use `gt agents` to list agents — not `gt status --agents` (incorrect flag).

## Agent Configuration

Gastown agents run the `claude` CLI. The environment is configured so that every `claude` process talks to Kimi:

```
ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
ANTHROPIC_API_KEY=<kimi-key-from-pool>
CLAUDE_CONFIG_DIR=~/.claude-kimigas
DISABLE_COST_WARNINGS=true
```

The Claude config at `~/.claude-kimigas/.claude.json` handles:
- Permission bypass (`bypassPermissionsModeAccepted: true`)
- API key approval (`customApiKeyResponses.approved`)
- Onboarding skip (`hasCompletedOnboarding: true`)

## Kimi Account Setup

Each Gastown agent can use a different Kimi key. Keys are distributed via `setup_kimi_accounts()`:

```
~/.kimi-accounts/
├── 1/config.toml   # Key 1
├── 2/config.toml   # Key 2
└── 3/config.toml   # Key 3
```

The active key is selected by the `KeyPool` LRU algorithm (see [Kimi Proxy Guide](kimi-proxy.md)).

## Beads Integration

Beads (`bd`) provides git-backed issue tracking for agents:

```bash
bd create --name "task-123" --content "Fix bug in parser"
bd list                    # List all beads
bd search --query "parser" # Search beads
bd close --name "task-123" # Mark complete
```

Bead state is backed by Dolt SQL and survives container restarts. OpenClaw agents are instructed to use beads for all memory and state tracking instead of plain markdown files.

## Troubleshooting

### `gt install` fails

- Verify Go is installed: `go version`
- Verify `gt` is in PATH: `which gt`
- Check `/workspace/gt` is writable

### `gt rig add` fails silently

- Must be run from the `gt_root` directory
- In code: `subprocess.run(["gt", "rig", "add", url], cwd=str(gt_root), check=True)`

### Daemon won't start

- Check if already running: `pgrep -f "gt daemon"`
- Check logs: `cat /workspace/gt/daemon.log`
- Kill stale process: `pkill -f "gt daemon"`

### Mayor exits immediately

- Ensure daemon is running first
- Ensure the agent name matches what was configured: `gt config default-agent`
- Check Kimi API key is valid (the `claude` process will fail if the backend rejects the key)
