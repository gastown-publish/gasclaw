# Knowledge Base / FAQ

Lessons learned from building, deploying, and debugging Gasclaw. This document covers real issues encountered in production and their solutions.

---

## Gastown Integration

### Q: What is the "real" Gastown?

Gastown is a Go-based multi-agent orchestration system at [github.com/steveyegge/gastown](https://github.com/steveyegge/gastown). It provides the `gt` CLI for managing agent workspaces, along with a companion tool `bd` (beads) for git-backed issue tracking.

**The correct way to install Gastown in a Dockerfile:**

```dockerfile
RUN go install github.com/steveyegge/gastown/cmd/gt@latest
RUN go install github.com/steveyegge/beads/cmd/bd@latest
```

Do **not** use `pip install gastown` — that installs a different (incorrect) package.

### Q: What `gt` subcommands does Gasclaw use?

| Command | Purpose |
|---------|---------|
| `gt install` | Initialize the Gastown workspace |
| `gt rig add <url>` | Register a project repository |
| `gt config agent set <name> <cmd>` | Register a named agent |
| `gt config default-agent <name>` | Set the default agent |
| `gt daemon start` / `gt daemon stop` | Manage the daemon process |
| `gt mayor start --agent <name>` | Start the mayor agent |
| `gt agents` | List running agents (not `gt status --agents`) |

### Q: Why does `gt rig add` need `cwd=gt_root`?

The `gt rig add` command must be run from the Gastown installation directory (`/workspace/gt`). Without the correct `cwd`, it fails silently or creates the rig in the wrong location.

---

## Kimi Proxy / Claude Code Backend

### Q: How does Kimi work as the Claude Code backend?

Claude Code CLI reads `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY` from the environment. By setting:

```bash
ANTHROPIC_BASE_URL=https://api.kimi.com/coding/
ANTHROPIC_API_KEY=<your-kimi-key>
```

...every `claude` invocation talks to Kimi K2.5 instead of Anthropic. This is handled automatically by `build_claude_env()` in `kimigas/proxy.py`.

### Q: Why can't we use `--dangerously-skip-permissions`?

The `--dangerously-skip-permissions` flag is **rejected when running as root** (which is common in Docker containers). Instead, Gasclaw writes a Claude config file that pre-approves permissions:

```json
{
  "hasCompletedOnboarding": true,
  "bypassPermissionsModeAccepted": true,
  "customApiKeyResponses": {
    "approved": ["<last-20-chars-of-api-key>"]
  }
}
```

This is written by `write_claude_config()` in `kimigas/proxy.py` to an isolated config directory (`~/.claude-kimigas`). The `CLAUDE_CONFIG_DIR` env var points Claude CLI to this directory.

### Q: How does key rotation work?

The `KeyPool` class in `kimigas/key_pool.py` implements LRU (Least Recently Used) rotation:

1. Keys are sorted by last-use timestamp
2. `get_key()` returns the least-recently-used available key
3. When a key hits a 429 (rate limit), call `report_rate_limit(key)` to quarantine it for 5 minutes
4. If ALL keys are rate-limited, the pool returns the key closest to cooldown expiry (graceful degradation)
5. State is tracked by BLAKE2b hash — raw keys are never persisted to disk

**Minimum recommendation:** 2-3 keys for uninterrupted service.

### Q: Why are Gastown and OpenClaw keys separate?

| Pool | Env Var | Purpose |
|------|---------|---------|
| Gastown | `GASTOWN_KIMI_KEYS` | Agent workers (Mayor, Crew) |
| OpenClaw | `OPENCLAW_KIMI_KEY` | Overseer bot (Telegram, monitoring) |

Separating pools ensures the overseer can always function even when all agent keys are rate-limited. Never put the same key in both pools.

---

## OpenClaw & Telegram

### Q: Why doesn't the bot respond to messages?

This is the most common issue. Check in order:

1. **Is the gateway running?**
   ```bash
   curl http://localhost:18789/health
   ```

2. **Is `dmPolicy` set to `"open"`?**
   If set to `"allowlist"`, only users in `allowFrom` can talk to the bot. For open access, set `dmPolicy: "open"` and `allowFrom: ["*"]`.

3. **Is `groupPolicy` set to `"open"`?**
   Valid values: `"open"`, `"disabled"`, `"allowlist"`. The value `"owner"` does **not** exist and will be silently ignored.

4. **Is `requireMention` disabled for groups?**
   By default, OpenClaw requires @mention in groups. You must set `channels.telegram.groups: { "*": { "requireMention": false } }` to make the bot reply to all group messages. The `ackReactionScope` only controls the acknowledgment emoji reaction — it does NOT control whether the bot actually replies.

5. **Is the bot an admin or is privacy mode disabled?**
   Telegram bots have Privacy Mode enabled by default, which blocks them from seeing group messages unless @mentioned. Either make the bot a group admin, or disable privacy mode via BotFather (`/setprivacy` -> Disable). After changing privacy mode, remove and re-add the bot to each group.

6. **Is `streaming` off?**
   Some Telegram setups don't support streaming. Set `streaming: "off"`.

### Q: What is the correct OpenClaw Telegram config?

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "botToken": "YOUR_TOKEN",
      "dmPolicy": "open",
      "allowFrom": ["*"],
      "groupPolicy": "open",
      "groups": { "*": { "requireMention": false } },
      "streaming": "off"
    }
  },
  "messages": {
    "ackReactionScope": "all"
  }
}
```

Key fields:

| Field | Value | Why |
|-------|-------|-----|
| `dmPolicy` | `"open"` | Accept DMs from everyone |
| `allowFrom` | `["*"]` | Required when `dmPolicy` is `"open"` |
| `groupPolicy` | `"open"` | Accept all group senders |
| `groups.*. requireMention` | `false` | Reply to all group messages without @mention |
| `ackReactionScope` | `"all"` | Show acknowledgment reaction on all messages |
| `streaming` | `"off"` | Avoid Telegram streaming issues |

**Important:** `ackReactionScope` only controls the emoji reaction — it does NOT make the bot reply. The `groups.*.requireMention: false` setting is what actually disables the @mention requirement for group replies.

### Q: What values does `groupPolicy` accept?

Only these three: `"open"`, `"disabled"`, `"allowlist"`. The value `"owner"` was tried during debugging and does **not** work — it is silently ignored by OpenClaw.

### Q: How do I add the bot to a group?

1. Add the bot to the Telegram group
2. Set `groupPolicy: "open"` in `openclaw.json`
3. Set `ackReactionScope: "all"` so the bot responds to all messages, not just @mentions
4. Restart the gateway: `openclaw gateway stop && openclaw gateway start`

### Q: OpenClaw overwrites my config on restart!

The `entrypoint.sh` in the maintainer container writes `openclaw.json` on every startup (step 9). Manual `openclaw config set` changes will be overwritten. To make permanent changes:

1. Edit `src/gasclaw/openclaw/installer.py` (for the Python module)
2. Edit `maintainer/entrypoint.sh` step 9 (for the Docker container)
3. Both must be in sync

---

## Docker / Container Issues

### Q: Why does the container crash loop?

The most common cause is a file permission error in `entrypoint.sh`. Since the script uses `set -euo pipefail`, any failing command kills the container.

**Common triggers:**

| Command | Failure | Fix |
|---------|---------|-----|
| `cp /opt/agent-soul.md "$AGENT_WORKSPACE/SOUL.md"` | Permission denied (UID mismatch) | `chown -R 1000:1000 /workspace/` |
| `dolt sql-server` | Port 3307 already in use | `pkill -f "dolt sql-server"` |
| `gt daemon run` | GT_HOME not writable | Check directory permissions |

**Diagnosing crash loops:**

```bash
docker logs <container_id> --tail 50
docker exec -u root <container_id> ls -la /workspace/
```

### Q: Why do file permissions fail in the container?

Docker volumes may be owned by a different UID than the container user. The `maintainer` user (UID 1000) needs to own `/workspace/`:

```bash
docker exec -u root <container_id> chown -R 1000:1000 /workspace/
```

### Q: How does Dolt get stopped reliably?

The old approach `dolt sql-server --stop` was unreliable in containers. Gasclaw now uses:

```python
subprocess.run(["pkill", "-f", "dolt sql-server"], check=True)
```

This ensures the Dolt process is terminated regardless of its state.

---

## Bootstrap & Health

### Q: What is the bootstrap sequence?

The 10-step bootstrap in `bootstrap.py`:

| Step | Action | What Happens |
|------|--------|--------------|
| 1 | Setup Kimi proxy | Write kimi accounts, init KeyPool, set `ANTHROPIC_BASE_URL`, write Claude config |
| 2 | Install Gastown | `gt install` + `gt rig add` |
| 3 | Configure agent | `gt config agent set kimi-claude claude` + set as default |
| 4 | Start Dolt | Launch Dolt SQL server on configured port |
| 5 | Configure OpenClaw | Write `~/.openclaw/openclaw.json` |
| 6 | Install skills | Copy skills to `~/.openclaw/skills/` |
| 7 | Run doctor | `openclaw doctor --repair` |
| 8 | Start daemon | `gt daemon start` |
| 9 | Start mayor | `gt mayor start --agent kimi-claude` |
| 10 | Notify | Send "Gasclaw is up" via Telegram |

If any step fails, all previously started services are rolled back automatically.

### Q: What health checks are performed?

| Service | Method | Healthy When |
|---------|--------|--------------|
| Dolt | `dolt sql -q "SELECT 1"` | Query returns successfully |
| Daemon | `gt daemon status` | Process is running |
| Mayor | `gt mayor status` | Process is running |
| OpenClaw | `GET http://localhost:18789/health` | HTTP 200 |
| Activity | `git log --since=<deadline>` | Commits exist within deadline |

### Q: What does `gt agents` return vs `gt status --agents`?

Use `gt agents` (correct). The flag `--agents` on `gt status` does not exist and will error.

---

## Testing

### Q: How do I run the tests?

```bash
make test          # 954 unit tests (no API keys or services needed)
make test-all      # Includes integration tests
make lint          # Ruff linting
```

### Q: Why do tests hang?

If bootstrap-related tests hang, it's usually because `os.environ.update()` is leaking real environment changes. Fix by patching:

```python
@patch("gasclaw.bootstrap.build_claude_env", return_value={})
@patch("gasclaw.bootstrap.write_claude_config")
def test_bootstrap(mock_config, mock_env, ...):
    ...
```

### Q: Should I modify tests to make them pass?

**No.** The project rule is: never modify a test to make it pass — fix the code. Tests define the contract.

### Q: What mocking patterns are used?

- **subprocess calls**: `monkeypatch.setattr("subprocess.run", ...)` or `@patch("subprocess.run")`
- **HTTP calls**: `respx` for mocking `httpx` requests
- **File I/O**: `tmp_path` fixture for isolated file operations
- **Environment**: `monkeypatch.setenv()` and `monkeypatch.delenv()`

---

## Configuration

### Q: Where does OpenClaw config live?

`~/.openclaw/openclaw.json` — written by `write_openclaw_config()` in `src/gasclaw/openclaw/installer.py`.

### Q: Where does the Claude config live?

`~/.claude-kimigas/.claude.json` — written by `write_claude_config()` in `src/gasclaw/kimigas/proxy.py`. The path is set via `CLAUDE_CONFIG_DIR`.

### Q: Where are Kimi accounts stored?

`~/.kimi-accounts/<n>/config.toml` — one per key, written by `setup_kimi_accounts()` in `gastown/installer.py`.

### Q: How do I add a new environment variable?

1. Add field to `GasclawConfig` dataclass in `config.py`
2. Add env var parsing in `load_config()`
3. Add tests in `tests/unit/test_config.py`
4. Add to the env var tables in docs

---

## Git & Contributing

### Q: What branch naming convention is used?

- `fix/` — Bug fixes
- `feat/` — New features
- `test/` — Test additions
- `docs/` — Documentation
- `refactor/` — Code restructuring

### Q: What's the commit message format?

```
<type>: <description>

Examples:
fix: integrate real Gastown CLI and correct subprocess commands
feat: add KeyPool LRU rotation for Kimi keys
docs: update architecture and troubleshooting guides
```

### Q: What should every PR include?

- All 954 tests passing (`make test`)
- Lint passing (`make lint`)
- New code has corresponding tests
- Commit message follows `<type>: <description>`
- PR description with summary and test plan
