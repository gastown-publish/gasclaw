# Troubleshooting

## Bootstrap Failures

| Error | Cause | Fix |
|-------|-------|-----|
| "GASTOWN_KIMI_KEYS is not set" | Missing env var | `export GASTOWN_KIMI_KEYS="sk-key1:sk-key2"` |
| "TELEGRAM_OWNER_ID must be numeric" | Non-numeric ID | Use numeric ID, not @username |
| "Dolt process exited early" | Port conflict | `pkill -f "dolt sql-server"` or change `DOLT_PORT` |
| "openclaw not found" | Not installed | `npm install -g openclaw` |

## Telegram Bot Not Responding

Check in order:

1. **Gateway running?** `curl http://localhost:18789/health`
2. **Config correct?** Verify `dmPolicy: "open"`, `allowFrom: ["*"]`, `groupPolicy: "open"`
3. **Group replies?** Set `groups.*.requireMention: false` (default is `true`)
4. **Privacy mode?** Disable via BotFather `/setprivacy` or make bot admin
5. **Check logs:** `openclaw logs` or `tail /workspace/logs/openclaw-gateway.log`
6. **Valid token?** `curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"`

## Key / Rate Limit Issues

| Issue | Fix |
|-------|-----|
| HTTP 429 (rate limit) | Wait 5 min (auto-cooldown) or add more keys |
| All keys exhausted | Pool returns key closest to cooldown expiry |
| Claude prompts for API key | Check `CLAUDE_CONFIG_DIR` and `.claude.json` |

## Container Issues

| Issue | Fix |
|-------|-----|
| Crash loop | Check `docker logs`, usually permission errors. Run `chown -R 1000:1000 /workspace/` |
| UID mismatch | `docker exec -u root <id> chown -R 1000:1000 /workspace/` |
| Config overwritten | Edit source files, not `openclaw config set` |
| Dolt won't stop | `pkill -f "dolt sql-server"` |

## Debugging

```bash
# Logs
openclaw logs
cat /workspace/gt/daemon.log

# Config validation
bash scripts/validate-openclaw-config.sh
openclaw doctor --repair
openclaw channels status --probe

# Process check
ps aux | grep -E "dolt|gt|openclaw|claude"

# Test Telegram
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TELEGRAM_OWNER_ID}" -d text="Test"
```
