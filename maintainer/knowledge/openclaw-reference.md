# OpenClaw — Condensed Operational Reference

## Key Commands
```
openclaw status                     # Overall health
openclaw gateway status             # Gateway process status
openclaw gateway restart            # Restart gateway
openclaw logs --follow              # Tail gateway logs
openclaw doctor --fix --yes         # Auto-fix common issues
openclaw channels status --probe    # Channel connectivity test
openclaw agents list --bindings     # Show all agents + routing
openclaw cron list                  # Show scheduled jobs
openclaw config validate            # Validate openclaw.json
openclaw skills list -v             # List loaded skills
openclaw memory search "query"      # Search agent memory
```

## Config: ~/.openclaw/openclaw.json
- `agents.list[]`: Each agent has `id`, `workspace`, `agentDir`, `identity`, `tools`
- `agents.defaults.model`: Default model for all agents
- `bindings[]`: Routes inbound messages to agents by channel/peer/account
- `tools.agentToAgent.enabled`: Cross-agent messaging
- `channels.telegram.groups.<id>.topics.<threadId>`: Per-topic config

## Telegram Actions (agents can use)
- `sendMessage`: `{action:"send", channel:"telegram", to:"chatId", content:"text", messageThreadId: N}`
- `editMessage`: `{action:"edit", channel:"telegram", chatId:"...", messageId:N, content:"..."}`
- `createForumTopic`: `{action:"topic-create", channel:"telegram", chatId:"...", name:"..."}`
- `react`: `{action:"react", channel:"telegram", chatId:"...", messageId:N, emoji:"👍"}`

## Topic Session Keys
Format: `agent:<agentId>:telegram:default:<groupId>:topic:<threadId>`
Topics isolate sessions — each topic has its own conversation history.

## Troubleshooting Ladder
1. `openclaw status` → check gateway running
2. `openclaw logs --follow` → look for errors
3. `openclaw doctor --fix --yes` → auto-repair
4. `openclaw channels status --probe` → verify Telegram connected
5. `pgrep -f openclaw-gateway` → process alive?
6. If dead: `pkill -f openclaw-gateway; sleep 2; nohup openclaw gateway run >> /workspace/logs/openclaw-gateway.log 2>&1 &`

## DM/Group Policies
- `dmPolicy`: pairing (default), allowlist, open, disabled
- `groupPolicy`: allowlist (default), open, disabled
- `requireMention`: true/false per group/topic
- `allowFrom`/`groupAllowFrom`: numeric Telegram user IDs

## Skills
- Workspace skills: `<workspace>/skills/`
- Shared skills: `~/.openclaw/skills/`
- Each skill needs `SKILL.md` with YAML frontmatter
- Skills snapshot at session start; changes apply next session

## Agent-to-Agent Communication
Enabled via `tools.agentToAgent.enabled: true` + `allow` list.
Agents can message each other via the `sessions_send` tool.
Coordinator delegates to specialists; specialists report back.

## Cron Jobs
```
openclaw cron add --name <name> --cron "<expr>" --agent <id> --message "..." --no-deliver
openclaw cron list
openclaw cron remove <id>
```
Use `--no-deliver` to prevent dumping to General; agents post to topics themselves.
