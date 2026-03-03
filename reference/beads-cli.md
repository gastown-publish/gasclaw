# Beads (`bd`) CLI — Quick Reference

Source: https://github.com/steveyegge/beads

Git-backed issue tracking used by Gastown agents for state and memory.

## Installation

```bash
go install github.com/steveyegge/beads/cmd/bd@latest
```

## Key Commands

```bash
bd create --name "task-123" --content "Fix parser bug"   # Create a bead
bd list                                                    # List all beads
bd search --query "parser"                                 # Search beads
bd show <id>                                               # Show bead details
bd update <id> <field> <value>                             # Update a bead
bd close --name "task-123"                                 # Close/complete a bead
```

## Usage in Gasclaw

- Beads are the primary memory/state system for agents
- Backed by Dolt SQL — survives container restarts
- OpenClaw agents should use `bd` for ALL persistent state, not markdown files
- Set `BD_ROOT` env var to point to the Gastown workspace

## Agent Instructions

Agents receive these instructions:
> Use beads (bd CLI) for ALL memory and state tracking.
> Never use plain markdown memory files.
> Use 'bd create' to record tasks, decisions, and state.
> Use 'bd list' and 'bd search' to recall past context.
> Use 'bd close' when tasks are done.
