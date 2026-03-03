# Kimi K2.5 Proxy — Quick Reference

All Gasclaw agents use Kimi K2.5 as LLM backend via Claude Code CLI.

## How It Works

Claude Code reads these env vars:

```bash
ANTHROPIC_BASE_URL=https://api.kimi.com/coding/   # Redirect to Kimi
ANTHROPIC_API_KEY=<kimi-api-key>                   # Kimi auth
CLAUDE_CONFIG_DIR=~/.claude-kimigas                # Isolated config
DISABLE_COST_WARNINGS=true                         # Suppress warnings
```

## Permission Bypass

`--dangerously-skip-permissions` is rejected under root. Use Claude config file instead:

```json
// ~/.claude-kimigas/.claude.json
{
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true,
  "customApiKeyResponses": {
    "approved": ["<last-20-chars-of-api-key>"]
  }
}
```

Also create `~/.claude-kimigas/.credentials.json` as `{}`.

## Key Pools

| Pool | Env Var | Used By |
|------|---------|---------|
| Gastown agents | `GASTOWN_KIMI_KEYS` (colon-separated) | Mayor, Crew, Daemon |
| OpenClaw overseer | `OPENCLAW_KIMI_KEY` (single key) | Telegram bot |

Pools are NEVER shared. Overseer always works even when agent keys exhausted.

## LRU Rotation

1. `get_key()` returns least-recently-used available key
2. On HTTP 429: `report_rate_limit(key)` → quarantined 5 minutes
3. All keys exhausted → returns key closest to cooldown expiry
4. Keys tracked by BLAKE2b hash — never stored in plaintext

## Validate Key

```bash
curl -H "Authorization: Bearer sk-xxx" https://api.kimi.com/coding/v1/models
```
