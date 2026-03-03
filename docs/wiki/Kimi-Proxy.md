# Kimi Proxy & Key Rotation

All Gasclaw agents use Kimi K2.5 via Claude Code's CLI interface.

## How It Works

Claude Code reads environment variables to redirect API calls:

| Variable | Value | Purpose |
|----------|-------|---------|
| `ANTHROPIC_BASE_URL` | `https://api.kimi.com/coding/` | Redirect to Kimi |
| `ANTHROPIC_API_KEY` | `<kimi-key>` | Kimi authentication |
| `CLAUDE_CONFIG_DIR` | `~/.claude-kimigas` | Isolated config dir |
| `DISABLE_COST_WARNINGS` | `true` | Suppress Anthropic warnings |

## Permission Bypass

`--dangerously-skip-permissions` is rejected under root. Instead, `write_claude_config()` creates:

**`~/.claude-kimigas/.claude.json`:**
```json
{
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true,
  "customApiKeyResponses": {
    "approved": ["<last-20-chars-of-api-key>"]
  }
}
```

## Key Pool (LRU Rotation)

```
Available → In Use → Rate Limited → Cooldown (5 min) → Available
```

- `get_key()` returns least-recently-used key
- On HTTP 429: key quarantined for 5 minutes
- All keys exhausted: returns key closest to cooldown expiry
- Keys tracked by BLAKE2b hash, never stored in plaintext

## Separate Pools

| Pool | Env Var | Used By |
|------|---------|---------|
| Gastown | `GASTOWN_KIMI_KEYS` | Mayor, Crew |
| OpenClaw | `OPENCLAW_KIMI_KEY` | Overseer |

Never shared. Overseer always works even when agent keys are exhausted.

## Validate a Key

```bash
curl -H "Authorization: Bearer sk-xxx" https://api.kimi.com/coding/v1/models
```
