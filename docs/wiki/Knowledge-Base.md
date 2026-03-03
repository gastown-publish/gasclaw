# Knowledge Base / FAQ

Lessons learned from real production incidents.

## Gastown

**Q: What is the "real" Gastown?**
Go-based multi-agent system at [steveyegge/gastown](https://github.com/steveyegge/gastown). Install via `go install`, NOT `pip install gastown` (wrong package).

**Q: Why does `gt rig add` need `cwd=gt_root`?**
Must be run from the Gastown workspace directory or it fails silently.

**Q: `gt agents` vs `gt status --agents`?**
Use `gt agents`. The `--agents` flag on `gt status` does not exist.

## Kimi Proxy

**Q: How does Kimi work as Claude backend?**
Set `ANTHROPIC_BASE_URL=https://api.kimi.com/coding/` and `ANTHROPIC_API_KEY=<kimi-key>`. Every `claude` invocation talks to Kimi instead of Anthropic.

**Q: Why not `--dangerously-skip-permissions`?**
Rejected under root (common in Docker). Use Claude config file with `bypassPermissionsModeAccepted: true`.

**Q: Why are Gastown and OpenClaw keys separate?**
Ensures overseer always works even when all agent keys are rate-limited.

## OpenClaw & Telegram

**Q: Bot doesn't respond in groups?**
You need `groups.*.requireMention: false`. The `ackReactionScope: "all"` only controls the emoji reaction, NOT whether the bot replies.

**Q: What values does `groupPolicy` accept?**
Only `"open"`, `"disabled"`, `"allowlist"`. The value `"owner"` does NOT exist and is silently ignored.

**Q: Config keeps resetting?**
The container's `entrypoint.sh` rewrites `openclaw.json` on every startup. Edit source files: `src/gasclaw/openclaw/installer.py` and `maintainer/entrypoint.sh`.

**Q: `allowFrom` validation errors?**
When `dmPolicy: "open"`, you must set `allowFrom: ["*"]`. Never put group chat IDs in `allowFrom` — that's for DM user IDs only.

## Docker

**Q: Container crash loop?**
Most common cause: file permission error with `set -euo pipefail`. Fix: `docker exec -u root <id> chown -R 1000:1000 /workspace/`

**Q: Dolt won't stop?**
`dolt sql-server --stop` is unreliable in containers. Use `pkill -f "dolt sql-server"`.

## Testing

**Q: Test count?** 954 unit tests, all mocked, no API keys needed.

**Q: Tests hang?** Bootstrap tests may leak env vars. Patch `build_claude_env` and `write_claude_config`.

**Q: Modify tests to make them pass?** Never. Fix the code instead.

## Configuration Rules

1. **Read official docs** before changing any config
2. **Validate after every change** — `bash scripts/validate-openclaw-config.sh`
3. **Test end-to-end** — send a real message, check logs
4. **Never mix concerns** — `allowFrom` is DM only, group config is under `groups`
5. **Check logs** — `openclaw logs` or `tail /workspace/logs/openclaw-gateway.log`
6. **Invalid values are silently ignored** by OpenClaw — test to verify
