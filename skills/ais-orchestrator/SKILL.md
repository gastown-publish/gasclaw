---
name: ais-orchestrator
description: "PRIMARY execution skill. Run, monitor, and orchestrate all agent sessions in tmux via ais CLI. Use ais for ALL task execution — spawning sub-agents, inspecting output, rotating accounts on rate limits, and collecting results. Everything runs in tmux."
metadata:
  openclaw:
    emoji: "🕸️"
    os:
      - linux
      - darwin
    requires:
      bins:
        - ais
        - tmux
parameters:
  action:
    type: string
    description: "Action: create, ls, inspect, inject, watch, kill, accounts, status, patrol"
    required: true
  name:
    type: string
    description: Session name for create/inspect/inject/kill
    required: false
  agent:
    type: string
    description: "Agent type: claude or kimi (default: kimi)"
    required: false
  account:
    type: string
    description: "Account ID: cc1-cc3/hataricc/nicxxx for claude, 1-N for kimi"
    required: false
  cmd:
    type: string
    description: Command to inject after agent loads
    required: false
---

# AIS Orchestrator — Primary Execution Skill

**ais is the primary way to run everything.** All tasks, agents, and processes are managed through tmux sessions via `ais`. Never run long-lived processes outside tmux.

Source: https://github.com/gastown-publish/ais

## Core Principle

> Everything runs in tmux. Everything is inspected in tmux. Use `ais` for all execution.

## Quick Reference

```bash
# === LIFECYCLE ===
ais create <name> -a claude|kimi -A <account> [--yolo] [-c "cmd"] [-d dir]
ais ls                              # list all sessions
ais kill <name>                     # graceful shutdown
ais kill --all                      # kill everything

# === MONITORING ===
ais inspect <name> -n 100           # capture last 100 lines
ais inspect <name> --rate-limit     # check for rate limits
ais watch <name> -i 5               # live tail (every 5s)
ais watch <name> --until "DONE"     # watch until pattern
ais logs <name> -o file.log         # save full scrollback
ais status <name>                   # machine-readable status

# === INTERACTION ===
ais inject <name> "do the thing"    # send command
ais inject <name> "y"               # answer a prompt

# === ACCOUNTS ===
ais accounts                        # list all accounts
```

## Spawning Agents

### Claude Code Agent
```bash
ais create worker1 -a claude -A cc1 --yolo -c "fix the auth bug in src/auth.py"
```

### Kimi Code Agent (free)
```bash
ais create worker2 -a kimi -A 1 --yolo -c "write tests for src/utils.py"
```

### With working directory
```bash
ais create task1 -a claude -A cc2 --yolo -d ~/project/services/auth -c "fix all failing tests"
```

## Account Inventory

Check before spawning:
```bash
ais accounts
```

### Claude Code Accounts (~/.claude-accounts/)

| Account | Model | Best For |
|---------|-------|----------|
| `cc1` | Sonnet | Fast tasks, workers |
| `cc2` | Sonnet | Parallel workers |
| `cc3` | Opus | Complex reasoning |

Env: `CLAUDE_CONFIG_DIR=~/.claude-accounts/<id>`

### Kimi Code Accounts (~/.kimi-accounts/)

Free, no credit cost, has rate limits. Add more with `kimi-account add <key>`.

Env: `KIMI_SHARE_DIR=~/.kimi-accounts/<id>`

## The 7 Rules of Sub-Agent Prompts

1. **One task, one agent.** Never give an agent two unrelated goals.
2. **Be specific about what, not how.** Say "fix the failing test in `test_auth.py`" not "look at the tests."
3. **Name the files.** "Edit `src/auth/handler.py`" not "find the auth code."
4. **Set boundaries.** "Only modify files in `services/order/`."
5. **Define done.** "When done, print `TASK COMPLETE: <summary>`."
6. **Give context, not instructions to find context.** Paste the error, not "run the tests to see."
7. **Match agent to task.** Opus for architecture. Sonnet for fixes. Kimi for free boilerplate.

## Prompt Template

```
[WHAT] One sentence stating the task.
[CONTEXT] The error, test output, function signature.
[SCOPE] Which files to touch. Which to leave alone.
[DONE] How to signal completion.
[CONSTRAINTS] Things to avoid.
```

## Monitoring All Agents

### Quick patrol
```bash
bash ~/.openclaw/skills/ais-orchestrator/scripts/patrol.sh
```

### Manual check
```bash
for name in $(ais ls 2>/dev/null | tail -n +3 | awk '{print $1}'); do
  echo "=== $name ==="
  output=$(ais inspect "$name" -n 10 --rate-limit 2>/dev/null)
  if echo "$output" | grep -q "TASK COMPLETE"; then
    echo "[DONE] $(echo "$output" | grep 'TASK COMPLETE')"
  elif echo "$output" | grep -qiE 'rate.?limit|429'; then
    echo "[RATE LIMITED] — rotate account"
  else
    echo "$output" | tail -3
  fi
done
```

## Rate Limit Recovery

When `ais inspect --rate-limit` detects a limit:

1. Kill the session: `ais kill <name>`
2. Pick a different account
3. Respawn: `ais create <name> -a <agent> -A <new-account> ...`

Rotation order:
- Claude: cc1 → cc2 → cc3 → cc1
- Kimi: 1 → 2 → 3 → 1

## Multi-Agent Patterns

### Fan-Out: Same task across directories
```bash
for svc in order product payment; do
  ais create "fix-${svc}" -a kimi -A $((RANDOM % 3 + 1)) --yolo \
    -d ~/project/services/${svc}-service \
    -c "Fix all failing tests. Print TASK COMPLETE when done."
done
```

### Pipeline: Sequential dependencies
```bash
ais create phase1 -a claude -A cc3 --yolo -c "Design the interface. Print TASK COMPLETE."
# Wait for phase 1
while ! ais inspect phase1 -n 20 | grep -q "TASK COMPLETE"; do sleep 30; done
# Fan-out phase 2
ais create impl1 -a claude -A cc1 --yolo -c "Implement using the interface."
ais create impl2 -a kimi -A 1 --yolo -c "Implement the other part."
```

### Specialist Agents
```bash
ais create architect -a claude -A cc3 --yolo -c "Review and design. Write PLAN.md."
ais create implement -a claude -A cc1 --yolo -c "Implement plan from PLAN.md."
ais create tester -a kimi -A 1 --yolo -c "Write tests. Free credits."
```

## Log Trail

Every session creates logs at `~/.ais/logs/<name>/`:

```
~/.ais/logs/worker1/
├── events.log      # Timestamped events
├── snapshots.log   # TUI captures
├── status.json     # Machine-readable (for other agents)
└── prompt.txt      # Original task
```

Other agents can resume work:
```bash
ais status worker1                            # read status
cat ~/.ais/logs/worker1/prompt.txt            # read original task
ais create worker1 -a claude -A cc2 -c "$(cat ~/.ais/logs/worker1/prompt.txt)"
```

## Rules

1. **Always run `ais accounts` first** — know what's available
2. **Spread across accounts** — don't overload one account
3. **Monitor every 2-5 minutes** — catch problems early
4. **Rotate immediately on rate limit** — don't wait
5. **Use Kimi for simple tasks** — it's free
6. **Save logs before killing** — `ais kill --save`
7. **Never send Ctrl-C** — always `ais kill` for graceful shutdown
8. **Include TASK COMPLETE signals** in every prompt
9. **Report to user** — what's running, done, failed
10. **Everything in tmux** — never run agents outside `ais`
