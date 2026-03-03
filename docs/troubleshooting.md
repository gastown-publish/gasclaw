# Troubleshooting

Common issues and their solutions.

## Bootstrap Failures

### "GASTOWN_KIMI_KEYS is not set"

**Cause**: Required environment variable missing.

**Solution**:

```bash
export GASTOWN_KIMI_KEYS="sk-key1:sk-key2"
```

### "TELEGRAM_OWNER_ID must be numeric"

**Cause**: Owner ID contains non-numeric characters.

**Solution**:

```bash
# Correct
export TELEGRAM_OWNER_ID="2045995148"

# Incorrect
export TELEGRAM_OWNER_ID="@username"
```

### "Dolt process exited early"

**Cause**: Port conflict or existing Dolt instance.

**Solution**:

```bash
# Check if Dolt is already running
pgrep -f "dolt sql-server"

# Stop existing Dolt
dolt sql-server --stop

# Or use a different port
export DOLT_PORT=3308
```

### "openclaw not found"

**Cause**: OpenClaw CLI not installed or not in PATH.

**Solution**:

```bash
# Install OpenClaw
# (Follow OpenClaw installation instructions)

# Verify
which openclaw
```

## Telegram Issues

### Bot not responding to messages

**Symptoms**: Bot is online but doesn't answer.

**Diagnosis**:

```bash
# Check if gateway is accessible
curl http://localhost:18789/health

# Check owner ID
echo $TELEGRAM_OWNER_ID  # Should be numeric

# Check OpenClaw logs
openclaw logs
```

**Solutions**:

1. **Verify owner_id is integer**: Check `~/.openclaw/openclaw.json`:
   ```json
   {
     "channels": {
       "telegram": {
         "allowFrom": [999999999]  // Must be int, not string
       }
     }
   }
   ```

2. **Restart OpenClaw**:
   ```bash
   openclaw gateway stop
   openclaw gateway start
   ```

3. **Verify bot token**:
   ```bash
   curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
   ```

### Not receiving notifications

**Cause**: Gateway not running or wrong chat ID.

**Solution**:

```bash
# Check gateway health
curl http://localhost:18789/health

# Verify chat ID matches owner ID
# They should be the same for DMs
```

## Key and Rate Limiting

### "Rate limit exceeded"

**Symptoms**: API calls return 429 errors.

**Solution**:

1. Wait 5 minutes for cooldown
2. Add more keys to `GASTOWN_KIMI_KEYS`
3. Check key pool status via Telegram: `/keys`

### "No keys available"

**Cause**: All keys are rate-limited or invalid.

**Solution**:

```bash
# Check key validity
curl https://api.kimi.com/coding/v1/models \
  -H "Authorization: Bearer sk-your-key"

# Update keys
export GASTOWN_KIMI_KEYS="sk-newkey1:sk-newkey2"
```

## Activity Compliance

### "ACTIVITY ALERT: No commits"

**Cause**: No git activity within `ACTIVITY_DEADLINE`.

**Solution**:

This is working as intended. The alert reminds you to push code. To resolve:

```bash
# Make a commit
git add .
git commit -m "activity: keepalive"
git push
```

To adjust the deadline:

```bash
export ACTIVITY_DEADLINE=7200  # 2 hours
```

## Health Check Failures

### SERVICE DOWN: dolt

**Diagnosis**:

```bash
dolt sql --port 3307 -q "SELECT 1"
echo $?  # Should be 0
```

**Solution**:

```bash
# Restart Dolt
dolt sql-server --stop
dolt sql-server --port 3307 &
```

### SERVICE DOWN: daemon

**Solution**:

```bash
# Restart daemon
gt daemon stop
gt daemon start
```

### SERVICE DOWN: mayor

**Solution**:

```bash
# Restart mayor
gt mayor stop
gt mayor start --agent kimi-claude
```

### SERVICE DOWN: openclaw

**Solution**:

```bash
# Restart gateway
openclaw gateway stop
openclaw gateway start
```

## Debugging

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
python -m gasclaw
```

### Check Configuration

```python
python -c "
from gasclaw.config import load_config
config = load_config()
print(f'Keys: {len(config.gastown_kimi_keys)}')
print(f'Owner ID: {config.telegram_owner_id}')
print(f'Interval: {config.monitor_interval}')
"
```

### Run Doctor

```bash
openclaw doctor --repair
```

### Test Telegram

```bash
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_OWNER_ID}" \
  -d text="Test message"
```

## Getting Help

If issues persist:

1. Check logs: `openclaw logs`, `gt logs`
2. Run tests: `make test`
3. File an issue with logs and config (redact secrets)
