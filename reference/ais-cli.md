# AIS CLI — Quick Reference

Source: https://github.com/gastown-publish/ais

Scriptable AI agent session manager. **Primary execution layer** — everything runs in tmux via `ais`.

## Installation

```bash
curl -sL https://raw.githubusercontent.com/gastown-publish/ais/main/bin/ais \
  -o ~/.local/bin/ais && chmod +x ~/.local/bin/ais
```

## Session Lifecycle

```bash
ais create <name> -a claude|kimi -A <account> [--yolo] [-c "cmd"] [-d dir]
ais ls                              # list all sessions
ais kill <name>                     # graceful shutdown
ais kill <name> --save              # save logs, then kill
ais kill --all                      # kill everything
```

## Monitoring

```bash
ais inspect <name> -n 100           # capture last 100 lines
ais inspect <name> --rate-limit     # check for rate limits
ais watch <name> -i 5               # live tail every 5s
ais watch <name> --until "DONE"     # watch until pattern
ais logs <name> -o file.log         # save full scrollback
ais status <name>                   # machine-readable JSON status
```

## Interaction

```bash
ais inject <name> "run the tests"   # send command
ais inject <name> "y"               # answer a prompt
ais inject <name> "" --no-enter     # send text without Enter
```

## Accounts

```bash
ais accounts                        # list all configured accounts
```

Claude: `~/.claude-accounts/<id>/` (cc1, cc2, cc3, etc.)
Kimi: `~/.kimi-accounts/<id>/` (1, 2, 3, etc.)

## Create Options

| Flag | Description |
|------|-------------|
| `-a, --agent` | `claude` or `kimi` (default: kimi) |
| `-A, --account` | Account ID |
| `-c, --cmd` | Command to inject after agent loads |
| `-d, --dir` | Working directory |
| `--yolo` | Auto-approve mode |
| `--attach` | Attach to session after creation |
| `--size WxH` | Terminal size (default: 160x50) |
| `--` | Pass remaining flags to agent CLI |

## Log Trail

Every session logs to `~/.ais/logs/<name>/`:
- `events.log` — timestamped events
- `snapshots.log` — TUI captures
- `status.json` — machine-readable status
- `prompt.txt` — original task prompt

## Rate Limit Detection

```bash
ais inspect <name> --rate-limit
```

Pattern: `rate.?limit|429|overloaded|quota.?exceeded`

Recovery: kill session, respawn with different account.

## Key Rules

1. Everything runs in tmux via `ais`
2. Always check `ais accounts` before spawning
3. Spread agents across accounts
4. Include "TASK COMPLETE" signal in every prompt
5. Use `ais kill` (never Ctrl-C) for graceful shutdown
6. Save logs before killing: `ais kill --save`
7. Use Kimi for simple tasks (free), Claude for complex ones
