# Gasclaw Architecture — System Knowledge

## Overview
Single Docker container running: OpenClaw + Gastown + KimiGas + AIS + Dolt + Beads + Tailscale.

## Component Map
```
┌─────────────────────────────────────────────────────┐
│  Docker Container (gasclaw-maintainer)              │
│                                                      │
│  ┌──────────────┐  ┌───────────────────┐            │
│  │  OpenClaw     │  │  Gastown (gt)     │            │
│  │  Gateway      │  │  ├─ Mayor         │            │
│  │  ├─ Telegram  │  │  ├─ Deacon        │            │
│  │  ├─ Cron jobs │  │  ├─ Witness       │            │
│  │  ├─ 10 agents │  │  ├─ Refinery      │            │
│  │  └─ Skills    │  │  └─ Crew workers  │            │
│  └──────────────┘  └───────────────────┘            │
│                                                      │
│  ┌──────────────┐  ┌───────────────────┐            │
│  │  AIS          │  │  Dolt DB          │            │
│  │  (tmux mgr)   │  │  (port 3307)     │            │
│  └──────────────┘  └───────────────────┘            │
│                                                      │
│  ┌──────────────┐  ┌───────────────────┐            │
│  │  Kimi Proxy   │  │  Beads (bd)       │            │
│  │  (API bridge) │  │  (git memory)     │            │
│  └──────────────┘  └───────────────────┘            │
└─────────────────────────────────────────────────────┘
```

## Agent Team (10 agents)
| ID | Role | Topic | Tools |
|----|------|-------|-------|
| coordinator | Tech Lead (default) | 462 | exec,read,write,sessions |
| sys-architect | System Architect | 463 | exec,read,write,edit |
| backend-dev | Backend Developer | 464 | exec,read,write,edit,apply_patch |
| db-engineer | Database Engineer | 465 | exec,read,write,edit |
| devops | DevOps Engineer | 466 | exec,read,write,edit |
| security-auditor | Security Auditor | 467 | exec,read |
| test-engineer | Test Engineer | 468 | exec,read,write,edit |
| api-docs | Documentation Writer | 469 | exec,read,write,edit |
| code-reviewer | Code Reviewer | 470 | exec,read |
| doctor | Infrastructure Doctor | 477 | exec,read,sessions |

## Key Paths
- Config: `/root/.openclaw/openclaw.json`
- Workspaces: `/root/.openclaw/workspace-<agent>/`
- Agent dirs: `/root/.openclaw/agents/<agent>/agent/`
- Skills (shared): `/root/.openclaw/skills/`
- Knowledge: `/opt/knowledge/`
- Beads: `/workspace/beads/<agent>/`
- Logs: `/workspace/logs/`
- State: `/workspace/state/`
- Kimi accounts: `/root/.kimi-accounts/`
- Project repo: `/workspace/gasclaw/`
- Gastown data: `/workspace/gt/`

## Cron Jobs
| Job | Schedule | Agent | Topic |
|-----|----------|-------|-------|
| health-patrol | */5 min | doctor | 477 |
| gastown-status | */15 min | devops | 466 |
| test-runner | */30 min | test-engineer | 468 |
| pr-review | hourly | code-reviewer | 470 |
| security-scan | 2h | security-auditor | 467 |
| docs-update | 4h | api-docs | 469 |

## Beads (Persistent Memory)
Each agent has a git-backed beads DB at `/workspace/beads/<agent>/`.
Use `bd` CLI to create/query beads (issues, notes, learnings).
```bash
export BD_ROOT=/workspace/beads/<agent>
cd $BD_ROOT
bd new "title" --body "description"
bd list
bd show <id>
```

## Environment Variables
- GASTOWN_KIMI_KEYS: Colon-separated Kimi keys for Gastown agents
- OPENCLAW_KIMI_KEY / KIMI_API_KEY: Key for OpenClaw agents
- TELEGRAM_BOT_TOKEN: Bot token for @gasclaw_master_bot
- TELEGRAM_CHAT_ID: Group chat ID (-1003759869133)
- GITHUB_TOKEN: GitHub PAT for repo operations
- MAINTENANCE_REPO: Target repo (gastown-publish/gasclaw)
- BD_ROOT: Beads database root path

## Self-Healing Stack
1. Bash watchdog (PID 1 loop) runs gateway-watchdog.sh every 120s
2. OpenClaw cron "health-patrol" runs doctor agent every 5 min
3. Doctor agent checks gateway, Dolt, Gastown, tmux and fixes issues
4. Persistent AIS watchdog session for deep diagnostics
