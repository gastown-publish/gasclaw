# AIS — AI Session Manager Reference

## What is AIS
CLI tool for managing Claude/Kimi coding agent sessions in tmux.
Primary tool for spawning, monitoring, and controlling AI workers.

## Commands
```
ais create <name> [options]   # Create new session
ais ls                        # List all sessions
ais inspect <name>            # Capture current screen output
ais inject <name> <text>      # Send text into session
ais watch <name>              # Live-monitor session
ais logs <name>               # Save scrollback to file
ais kill <name|--all>         # Kill session(s)
ais accounts                  # List available Kimi/Claude accounts
```

## Create Options
```
-a, --agent TYPE     # Agent type: claude, kimi (default: kimi)
-A, --account ID     # Account: 1..N for kimi accounts
-c, --cmd TEXT       # Command to inject after agent loads
-d, --dir PATH       # Working directory
--yolo               # Auto-approve mode (no confirmations)
--attach             # Attach to session after creation
--size WxH           # Terminal size (default: 160x50)
```

## Common Patterns
```bash
# Spawn a kimi worker for a task
ais create fix-tests -a kimi -d /workspace/gasclaw --yolo \
  -c "Run make test, fix any failures, commit fixes"

# Monitor what it's doing
ais inspect fix-tests

# Send it a new instruction
ais inject fix-tests "Also run make lint after fixing"

# Kill when done
ais kill fix-tests

# Spawn a diagnostic agent
ais create doctor -a kimi --yolo \
  -c "Check openclaw gateway status, fix if broken"
```

## Kimi Accounts
Located at `/root/.kimi-accounts/`. Each account has its own API key.
Account rotation handles rate limits — if one key is rate-limited, use another.

## Integration with OpenClaw
OpenClaw agents can spawn AIS sessions via `exec` tool:
```bash
ais create worker-1 -a kimi -d /workspace/gasclaw --yolo -c "task description"
```
Then monitor with `ais inspect worker-1` and kill with `ais kill worker-1`.
