# Dolt SQL Server — Quick Reference

Source: https://github.com/dolthub/dolt

Version-controlled SQL database used by Gastown for agent state.

## Installation

```bash
curl -fsSL https://github.com/dolthub/dolt/releases/latest/download/dolt-linux-amd64.tar.gz | \
  tar -C /usr/local/bin -xzf - --strip-components=1 dolt-linux-amd64/bin/dolt
```

## Server Management

```bash
# Start server
nohup dolt sql-server --port 3307 --data-dir /workspace/gt/.dolt-data \
  --max-connections 100 > dolt.log 2>&1 &

# Health check
dolt sql --port 3307 -q "SELECT 1"

# Stop (use pkill — dolt sql-server --stop is unreliable in containers)
pkill -f "dolt sql-server"
```

## Key Facts

- Default port: 3307 (configurable via `DOLT_PORT`)
- Data directory: `/workspace/gt/.dolt-data`
- Health check: `dolt sql -q "SELECT 1"` (exit code 0 = healthy)
- Used by Gastown for bead storage and agent state
- Git-like versioning: every write is committed
