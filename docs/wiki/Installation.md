# Installation

## Docker Deployment (Recommended)

Requirements: Docker Engine 24+, Docker Compose v2, 4GB+ RAM.

```bash
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw
cp .env.example .env   # Edit with your keys
docker compose up -d
```

## Local Development

Requirements: Python 3.11+, Go 1.24+, Node.js 22+, Git.

### 1. Clone and Setup Python

```bash
git clone git@github.com:gastown-publish/gasclaw.git
cd gasclaw
python -m venv .venv
source .venv/bin/activate
make dev
```

### 2. Install External Tools

```bash
# Gastown and Beads (Go)
go install github.com/steveyegge/gastown/cmd/gt@latest
go install github.com/steveyegge/beads/cmd/bd@latest

# Dolt
curl -fsSL https://github.com/dolthub/dolt/releases/latest/download/dolt-linux-amd64.tar.gz | \
  tar -C /usr/local/bin -xzf - --strip-components=1 dolt-linux-amd64/bin/dolt

# OpenClaw and Claude Code
npm install -g openclaw @anthropic-ai/claude-code
```

### 3. Verify

```bash
make test    # 954 unit tests — no API keys needed
```

## Next Steps

- [[Configuration]] — Set up environment variables
- [[Quick Start]] — Run your first bootstrap
- [[Architecture]] — Understand the system design
