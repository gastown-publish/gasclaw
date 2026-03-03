# Troubleshooting

Common issues and their solutions, organized by component. This guide is based on real production incidents.

---

## Bootstrap Failures

### "GASTOWN_KIMI_KEYS is not set"

**Cause**: Required environment variable missing.

```bash
export GASTOWN_KIMI_KEYS="sk-key1:sk-key2"
```

### "TELEGRAM_OWNER_ID must be numeric"

**Cause**: Owner ID contains non-numeric characters.

```bash
# Correct
export TELEGRAM_OWNER_ID="2045995148"

# Incorrect — will fail validation
export TELEGRAM_OWNER_ID="@username"
```

### "Dolt process exited early"

**Cause**: Port conflict or existing Dolt instance.

```bash
# Check if Dolt is already running
pgrep -f "dolt sql-server"

# Kill existing Dolt
pkill -f "dolt sql-server"

# Or use a different port
export DOLT_PORT=3308
```

### "openclaw not found"

**Cause**: OpenClaw CLI not installed or not in PATH.

```bash
npm install -g openclaw
which openclaw
```

### Bootstrap rollback messages

If you see "Bootstrap failed: ... Rolling back...", a step failed and Gasclaw is cleaning up. Check:

- Environment variables are set correctly
- All binaries (`gt`, `dolt`, `openclaw`, `claude`) are in PATH
- Port 3307 (Dolt) and 18789 (OpenClaw) are available
- Network connectivity for Telegram API

---

## Telegram Issues

### Bot not responding to messages

This is the most common issue. Check these in order:

**1. Is the gateway running?**
```bash
curl http://localhost:18789/health
```

**2. Check the OpenClaw config:**
```bash
cat ~/.openclaw/openclaw.json | python3 -m json.tool
```

Verify these fields:
```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "dmPolicy": "open",
      "allowFrom": ["*"],
      "groupPolicy": "open"
    }
  },
  "messages": {
    "ackReactionScope": "all"
  }
}
```

**3. Check the logs:**
```bash
openclaw logs
# Or in containers:
tail -f /workspace/logs/openclaw-gateway.log
```

**4. Verify the bot token:**
```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
```

**5. Restart the gateway:**
```bash
openclaw gateway stop
openclaw gateway start
```

### Bot requires @mention in groups

**Cause**: `ackReactionScope` is not set to `"all"`.

**Fix**:
```bash
openclaw config set messages.ackReactionScope all
```

Or in `openclaw.json`:
```json
{
  "messages": { "ackReactionScope": "all" }
}
```

### Bot only responds to owner

**Cause**: `dmPolicy` is set to `"allowlist"` with only the owner's ID.

**Fix**: Change to open policy:
```json
{
  "dmPolicy": "open",
  "allowFrom": ["*"]
}
```

When setting `dmPolicy: "open"`, OpenClaw **requires** `allowFrom: ["*"]`.

### groupPolicy "owner" doesn't work

**Cause**: `"owner"` is not a valid value for `groupPolicy`.

**Valid values**: `"open"`, `"disabled"`, `"allowlist"`. Invalid values are silently ignored.

**Fix**:
```json
{
  "groupPolicy": "open"
}
```

### Config changes lost after restart

**Cause**: The container's entrypoint script rewrites `openclaw.json` on every startup.

**Fix**: Edit the source files:
1. `src/gasclaw/openclaw/installer.py` — Python module
2. `maintainer/entrypoint.sh` step 9 — Docker entrypoint

Manual `openclaw config set` changes will be overwritten on next container restart.

### Not receiving notifications

**Cause**: Gateway not running or wrong chat ID.

```bash
# Check gateway health
curl http://localhost:18789/health

# Test sending a message directly
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_OWNER_ID}" \
  -d text="Test message"
```

---

## Key and Rate Limiting

### "Rate limit exceeded" / HTTP 429

**Cause**: API key hit Kimi's rate limit.

The KeyPool automatically quarantines rate-limited keys for 5 minutes. Options:

1. **Wait** — the key will be available again in ~5 minutes
2. **Add more keys** to `GASTOWN_KIMI_KEYS` for better distribution
3. **Check pool status** via Telegram: `/keys` or `gasclaw status`

### "No keys available"

**Cause**: All keys are rate-limited or invalid.

The pool will still return the key closest to cooldown expiry (graceful degradation). To fix permanently:

```bash
# Verify key validity
curl https://api.kimi.com/coding/v1/models \
  -H "Authorization: Bearer sk-your-key"

# Add more keys
export GASTOWN_KIMI_KEYS="sk-key1:sk-key2:sk-key3:sk-newkey4"
```

### Claude prompts for API key

**Cause**: `CLAUDE_CONFIG_DIR` not set or config file missing.

The fix is in `write_claude_config()` during bootstrap. Verify:

```bash
cat $CLAUDE_CONFIG_DIR/.claude.json
# Should show: bypassPermissionsModeAccepted: true
```

---

## Container Issues

### Container crash loop

**Cause**: `set -euo pipefail` in entrypoint means any command failure kills the container.

**Diagnosis**:
```bash
docker logs <container_id> --tail 50
```

**Most common cause**: File permission errors.

```bash
# Fix permissions
docker exec -u root <container_id> chown -R 1000:1000 /workspace/
```

### UID mismatch on volumes

**Cause**: Bind-mounted volumes have host UIDs that don't match the container user.

```bash
# Check current ownership
docker exec <container_id> ls -la /workspace/

# Fix
docker exec -u root <container_id> chown -R 1000:1000 /workspace/
```

### Dolt won't stop

**Cause**: `dolt sql-server --stop` is unreliable in containers.

Gasclaw uses `pkill -f "dolt sql-server"` instead.

```bash
pkill -f "dolt sql-server"
```

---

## Activity Compliance

### "ACTIVITY ALERT: No commits"

**Cause**: No git activity within `ACTIVITY_DEADLINE` (default: 3600s).

This is working as intended. The alert reminds you that agents haven't pushed code. To resolve:

```bash
# Check if agents are running
gt agents

# Check agent logs
cat /workspace/gt/daemon.log

# Adjust deadline if needed
export ACTIVITY_DEADLINE=7200  # 2 hours
```

---

## Health Check Failures

### SERVICE DOWN: dolt

```bash
dolt sql --port 3307 -q "SELECT 1"
# If fails, restart:
pkill -f "dolt sql-server"
nohup dolt sql-server --port 3307 &
```

### SERVICE DOWN: daemon

```bash
gt daemon stop
gt daemon start
```

### SERVICE DOWN: mayor

```bash
gt mayor stop
gt mayor start --agent kimi-claude
```

### SERVICE DOWN: openclaw

```bash
openclaw gateway stop
openclaw gateway start
```

---

## Debugging

### Enable debug logging

```bash
export LOG_LEVEL=DEBUG
python -m gasclaw
```

### Check configuration

```python
python -c "
from gasclaw.config import load_config
config = load_config()
print(f'Keys: {len(config.gastown_kimi_keys)}')
print(f'Owner ID: {config.telegram_owner_id}')
print(f'Interval: {config.monitor_interval}')
"
```

### Run doctor

```bash
openclaw doctor --repair
```

### Test Telegram manually

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_OWNER_ID}" \
  -d text="Test message from Gasclaw"
```

### Check all processes

```bash
ps aux | grep -E "dolt|gt|openclaw|claude"
```

---

## Getting Help

If issues persist:

1. Check logs: `openclaw logs`, `cat /workspace/gt/daemon.log`
2. Run tests: `make test`
3. Run doctor: `openclaw doctor --repair`
4. Check the [Knowledge Base](knowledge-base.md) for documented solutions
5. File an issue with logs and config (redact secrets)
