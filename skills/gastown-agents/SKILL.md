---
name: gastown-agents
description: Monitor, restart, and inspect individual Gastown agents
metadata:
  openclaw:
    emoji: 🤖
    os:
      - linux
    requires:
      bins:
        - gt
        - tmux
parameters:
  agent:
    type: string
    description: Name of the agent to manage (mayor, deacon, witness, refinery, crew-N)
    required: false
  action:
    type: string
    description: Action to perform (restart, logs, status, list)
    required: true
  lines:
    type: integer
    description: Number of log lines to show (for logs action)
    required: false
---

# Gastown Agent Manager

As the overseer, you monitor ALL agents and ensure they remain active and productive. Every agent must comply with the activity principle — no idle periods allowed.

## List All Agents

```bash
bash ~/.openclaw/skills/gastown-agents/scripts/agent-status.sh
```

Shows each agent's:
- Name and role
- tmux session status (alive/dead)
- Last activity timestamp
- Compliance status

## Restart an Agent

```bash
bash ~/.openclaw/skills/gastown-agents/scripts/agent-restart.sh <agent-name>
```

Examples:
```bash
bash ~/.openclaw/skills/gastown-agents/scripts/agent-restart.sh mayor
bash ~/.openclaw/skills/gastown-agents/scripts/agent-restart.sh crew-1
bash ~/.openclaw/skills/gastown-agents/scripts/agent-restart.sh deacon
```

## View Agent Logs

```bash
bash ~/.openclaw/skills/gastown-agents/scripts/agent-logs.sh <agent-name> [lines]
```

Examples:
```bash
bash ~/.openclaw/skills/gastown-agents/scripts/agent-logs.sh mayor 50
bash ~/.openclaw/skills/gastown-agents/scripts/agent-logs.sh crew-1 100
```

## Overseer Protocol

### Every 5 Minutes
1. Run agent-status.sh
2. Check: all agents alive? All compliant with activity?
3. If any agent dead → restart it
4. If any agent idle > 10 min → send it a nudge via `gt nudge`

### Every Hour
1. Check git log for recent commits/PRs
2. If no activity in 1 hour → escalate (restart mayor, reassign work)
3. Summarize mayor output and report to human

### Quality Assessment
- Check git log for commit quality (not just quantity)
- Look for: meaningful commit messages, test results, PR descriptions
- Flag agents producing low-quality work for review

## Agent Roles

| Agent | Role | Session |
|-------|------|---------|
| Mayor | Orchestrates all work | hq-mayor |
| Deacon | Code review, quality | hq-deacon |
| Witness | Testing, verification | hq-witness |
| Refinery | Dependencies, builds | hq-refinery |
| Crew-N | Individual workers | hq-crew-N |
