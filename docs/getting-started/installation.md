# Installation

## Requirements

### For Docker Deployment (Recommended)

- Docker Engine 24+
- Docker Compose v2
- 4GB+ RAM

Everything else is pre-installed in the container.

### For Local Development

- Python 3.12+
- Go 1.25+
- Node.js 22+
- Git
- Dolt
- Gastown CLI (`gt`) — from [steveyegge/gastown](https://github.com/steveyegge/gastown)
- Beads CLI (`bd`) — from [steveyegge/beads](https://github.com/steveyegge/beads)
- OpenClaw CLI — `npm install -g openclaw`
- Claude Code CLI — `npm install -g @anthropic-ai/claude-code`

## Docker Installation

```bash
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw
cp .env.example .env
# Edit .env with your keys
docker compose up -d
```

## Local Development Setup

### 1. Clone the Repository

```bash
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw
```

### 2. Set Up Python Environment

```bash
python -m venv .venv
source .venv/bin/activate
make dev
```

### 3. Install External Tools

**Gastown and Beads (Go):**
```bash
go install github.com/steveyegge/gastown/cmd/gt@latest
go install github.com/steveyegge/beads/cmd/bd@latest
```

**Dolt:**
```bash
# Linux
curl -fsSL https://github.com/dolthub/dolt/releases/latest/download/dolt-linux-amd64.tar.gz | \
  tar -C /usr/local/bin -xzf - --strip-components=1 dolt-linux-amd64/bin/dolt
```

**OpenClaw and Claude Code (Node.js):**
```bash
npm install -g openclaw @anthropic-ai/claude-code
```

## Verify Installation

Run the test suite:

```bash
make test
```

Expected output:

```
============================= test session starts ==============================
platform linux -- Python 3.13.x, pytest-9.x.x
collected 1021 items

tests/unit/... ............................................... [100%]

============================== 1021 passed in 12s ===============================
```

All 1021 unit tests run with mocked dependencies — no API keys or running services needed.

## Development Commands

```bash
make dev        # Install dev dependencies
make test       # Unit tests only (1021 tests)
make test-all   # All tests including integration
make lint       # Ruff linting
```

## Next Steps

- [Configure environment variables](configuration.md)
- [Run your first bootstrap](quickstart.md)
- [Understand the architecture](../architecture.md)
