---
name: gastown-update
description: "Check and apply updates to all Gastown dependencies: gt, Claude Code, OpenClaw, KimiGas, Dolt. Use when: checking for updates, applying updates, maintaining system currency."
metadata:
  { "openclaw": { "emoji": "🔄", "os": ["linux"], "requires": { "bins": ["npm", "pip"] } } }
---

# Gastown Update Manager

As the overseer, keep all dependencies up to date. Updates are checked every 6 hours automatically.

## Check for Updates

```bash
bash ~/.openclaw/skills/gastown-update/scripts/check-update.sh
```

Shows current versions of: gt, claude, openclaw, dolt, kimigas.

## Apply Updates

```bash
bash ~/.openclaw/skills/gastown-update/scripts/apply-update.sh
```

Updates all dependencies:
- `gt self-update`
- `npm update -g @anthropic-ai/claude-code openclaw`
- `pip install --upgrade kimi-cli`

## Update Strategy

1. Check versions first — only update if needed
2. Apply updates during low-activity periods
3. After updating, verify all services are still healthy
4. Notify the human owner of what was updated
