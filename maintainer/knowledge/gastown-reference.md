# Gastown (gt) — Condensed Operational Reference

## What is Gastown
Multi-agent AI workspace orchestrator (github.com/steveyegge/gastown).
Runs multiple Claude/Kimi agents in tmux sessions managing a git repo.

## Key Commands
```
gt status                    # Overall status (agents, rig, Dolt)
gt feed                      # Activity feed (recent agent actions)
gt up                        # Start all services (Dolt + daemon + mayor)
gt down                      # Stop all services
gt crew list                 # List crew workers
gt crew add <count>          # Add workers
gt crew restart              # Restart stuck workers
gt rig list                  # List rigs (projects)
gt rig add <url>             # Add a project rig
gt config agent list         # List agent configs
gt config agent set <name>   # Configure agent (model, flags, etc.)
gt daemon run                # Run the daemon (background)
```

## Architecture
- **Mayor**: Orchestrates work assignments (tmux: hq-mayor)
- **Deacon**: Monitors agent health (tmux: hq-deacon)
- **Witness**: Audits agent outputs (tmux: ga-witness)
- **Refinery**: Processes agent work (tmux: ga-refinery)
- **Crew**: Worker agents that do actual coding (tmux: ga-crew-N)
- **Dolt**: SQL database for state (port 3307)

## Agent Permission Fix (root containers)
Gastown passes `--dangerously-skip-permissions` by default, which fails as root.
Fix: `gt config agent set claude` to override the agent command, and set
`bypassPermissionsModeAccepted: true` in `~/.claude/.claude.json`.

## Common Issues
- **Agents stuck**: `gt crew restart` or kill tmux sessions manually
- **Dolt down**: `dolt sql -q "SELECT 1"` to test; restart with `gt up`
- **Rate limited**: Rotate Kimi keys in GASTOWN_KIMI_KEYS env var
- **No rig**: `gt rig add <url>` to add the project

## Tmux Sessions
```
tmux ls                              # List all sessions
tmux capture-pane -t <session> -p    # Read session output
tmux send-keys -t <session> "cmd" Enter  # Send command
```
