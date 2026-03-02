# Quick Start

This guide will get you up and running with Gasclaw in minutes.

## Prerequisites

Ensure you have:

1. Installed Gasclaw (`make dev`)
2. Set all [required environment variables](configuration.md)
3. Verified installation with `make test`

## Start Gasclaw

Run the bootstrap sequence:

```bash
python -m gasclaw
```

Or use the CLI:

```bash
gasclaw start
```

## Bootstrap Sequence

When you start Gasclaw, it runs a 13-step sequence:

1. **Setup Kimi accounts** - Configure API keys for agents
2. **Write agent config** - Create Gastown configuration
3. **Install Gastown** - Set up the rig and project
4. **Start Dolt** - Launch the SQL server
5. **Configure OpenClaw** - Write overseer configuration
6. **Install skills** - Copy OpenClaw skills to `~/.openclaw/skills/`
7. **Run doctor** - Verify system health
8. **Start OpenClaw gateway** - Launch the overseer
9. **Start gt daemon** - Launch Gastown daemon
10. **Start mayor** - Launch the mayor agent
11. **Send notification** - "Gasclaw is up and running"
12. **Enter monitor loop** - Continuous health checks

You'll see output like:

```
INFO  Setting up Kimi accounts (3 keys)
INFO  Writing agent config to /workspace/gt
INFO  Installing Gastown with rig_url=/project
INFO  Starting Dolt
INFO  Configuring OpenClaw in /root/.openclaw
INFO  Installing skills
INFO  Running openclaw doctor
INFO  Starting OpenClaw gateway
INFO  Starting gt daemon
INFO  Starting mayor agent
INFO  All services started successfully
INFO  Sending startup notification
INFO  Starting monitor loop with interval=300 seconds
```

## Verify It's Working

### Check Status

```bash
gasclaw status
```

### Send a Telegram Message

Send a message to your bot. It should respond if OpenClaw is running correctly.

### Check Logs

View OpenClaw logs:

```bash
openclaw logs
```

### Health Endpoint

Check the gateway health:

```bash
curl http://localhost:18789/health
```

## Stop Gasclaw

Press `Ctrl+C` to stop the monitor loop. The system will shut down gracefully.

Or use:

```bash
gasclaw stop
```

## What Happens Next

Once running, Gasclaw will:

1. **Check PRs** - Review and merge open PRs that pass tests
2. **Fix issues** - Work on open GitHub issues
3. **Maintain coverage** - Add tests for untested code
4. **Monitor health** - Watch all services and alert on failures
5. **Enforce activity** - Ensure code is committed every hour

You'll receive Telegram notifications for all significant events.

## Troubleshooting

If something goes wrong:

1. Check logs: `openclaw logs`
2. Verify env vars: `env | grep -E 'KIMI|TELEGRAM'`
3. Run doctor: `openclaw doctor --repair`
4. See [Troubleshooting](../troubleshooting.md) for common issues
