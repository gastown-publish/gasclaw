# Kimi Proxy & Key Rotation Guide

Gasclaw uses Kimi K2.5 as the LLM backend for all agents. This guide explains how the proxy works, how keys are managed, and how rotation handles rate limits.

## How the Proxy Works

Claude Code CLI supports custom API endpoints via environment variables. Gasclaw sets:

| Variable | Value | Purpose |
|----------|-------|---------|
| `ANTHROPIC_BASE_URL` | `https://api.kimi.com/coding/` | Redirect API calls to Kimi |
| `ANTHROPIC_API_KEY` | `<kimi-key>` | Authenticate with Kimi |
| `CLAUDE_CONFIG_DIR` | `~/.claude-kimigas` | Isolated config directory |
| `DISABLE_COST_WARNINGS` | `true` | Suppress Anthropic cost warnings |

When any `claude` process starts (Mayor, Crew, etc.), it reads these env vars and sends all requests to Kimi's endpoint instead of Anthropic's.

## The `build_claude_env()` Function

Located in `src/gasclaw/kimigas/proxy.py`:

```python
def build_claude_env(api_key: str, *, config_dir: str | None = None) -> dict[str, str]:
    return {
        "ANTHROPIC_BASE_URL": "https://api.kimi.com/coding/",
        "ANTHROPIC_API_KEY": api_key,
        "CLAUDE_CONFIG_DIR": config_dir or "~/.claude-kimigas",
        "DISABLE_COST_WARNINGS": "true",
    }
```

## Permission Bypass via Config File

The `--dangerously-skip-permissions` flag is **rejected when Claude Code runs as root** (common in Docker). Instead, `write_claude_config()` creates a config file that pre-approves permissions:

### What Gets Written

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

**`~/.claude-kimigas/.credentials.json`:**
```json
{}
```

### Why This Works

1. `bypassPermissionsModeAccepted: true` — Equivalent to the `--dangerously-skip-permissions` flag but works under root
2. `customApiKeyResponses.approved` — Pre-approves the API key fingerprint (last 20 chars) so Claude doesn't prompt for confirmation
3. `hasCompletedOnboarding: true` — Skips the first-run wizard
4. `CLAUDE_CONFIG_DIR` env var — Points Claude to this isolated config, avoiding conflicts with any existing Claude installation

## Key Pool Architecture

### Separate Pools

Gasclaw maintains **two completely independent key pools**:

| Pool | Env Var | Used By | Keys |
|------|---------|---------|------|
| Gastown | `GASTOWN_KIMI_KEYS` | Mayor, Crew, Daemon | Multiple (colon-separated) |
| OpenClaw | `OPENCLAW_KIMI_KEY` | Overseer bot | Single key |

Keys are **never shared** between pools. This ensures the overseer can always communicate via Telegram even when all agent keys are exhausted.

### LRU Rotation (`KeyPool`)

The `KeyPool` class in `src/gasclaw/kimigas/key_pool.py` implements Least-Recently-Used rotation:

```
Available ──► In Use ──► Rate Limited ──► Cooldown (5 min) ──► Available
```

**Algorithm:**

1. `get_key()` — Returns the key with the oldest last-use timestamp
2. On API call, the key's timestamp is updated
3. On HTTP 429 (rate limit), call `report_rate_limit(key)` — key is quarantined for 5 minutes (`RATE_LIMIT_COOLDOWN = 300`)
4. `is_available(key)` returns `False` during cooldown
5. If ALL keys are quarantined, the pool returns the key closest to cooldown expiry (graceful degradation, not a hard failure)

**State tracking:**

- Keys are identified by BLAKE2b hash — raw keys are never written to state files
- Rotation state persists across restarts via `key-rotation.json`

### Bootstrap Key Selection

During bootstrap, the KeyPool selects the initial key:

```python
pool = KeyPool(config.gastown_kimi_keys)
active_key = pool.get_key()
kimi_env = build_claude_env(active_key)
os.environ.update(kimi_env)
write_claude_config(active_key, config_dir=kimi_env["CLAUDE_CONFIG_DIR"])
```

## Key Management Commands

```bash
gasclaw status           # See pool state and key health
gasclaw keys --rotate    # Force-rotate current key (marks it rate-limited)
```

Via Telegram (OpenClaw skills):
- `/keys` — Show key pool status
- `/rotate` — Force key rotation

## Best Practices

1. **Minimum 2-3 keys** for uninterrupted service during rate limits
2. **Never share keys** between `GASTOWN_KIMI_KEYS` and `OPENCLAW_KIMI_KEY`
3. **Monitor the Kimi dashboard** for per-key usage and billing
4. **Rotate keys monthly** for security hygiene
5. **Test keys before deploying**: `curl -H "Authorization: Bearer sk-xxx" https://api.kimi.com/v1/users/me/balance`

## Troubleshooting

### "Rate limit exceeded" / HTTP 429

- Wait 5 minutes — the KeyPool automatically quarantines the key
- Add more keys to `GASTOWN_KIMI_KEYS`
- Check key pool status: `gasclaw status`

### "No keys available"

- All keys are either rate-limited or invalid
- The pool will still return the key closest to cooldown expiry
- Verify key validity: `curl -H "Authorization: Bearer sk-xxx" https://api.kimi.com/coding/v1/models`

### Claude prompts for API key interactively

- The `CLAUDE_CONFIG_DIR` env var is not set, so Claude is reading a different config
- The API key fingerprint in `.claude.json` doesn't match the current key
- Run `write_claude_config()` again with the current key

### Claude rejects `--dangerously-skip-permissions`

- You're running as root — this flag is rejected under root
- Remove the flag from the agent command
- Ensure `write_claude_config()` has been called (sets `bypassPermissionsModeAccepted: true`)
