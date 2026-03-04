FROM python:3.13-slim-bookworm

# --- Heavy layers (rarely change, cached) ---

# System deps + Node.js 22
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git tmux ca-certificates gnupg jq procps \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Claude Code + OpenClaw (pinned — only rebuild when versions change)
RUN npm install -g @anthropic-ai/claude-code openclaw

# PyYAML for config loader
RUN pip install --no-cache-dir pyyaml

# Go toolchain (for installing gt/bd if not bind-mounted)
COPY --from=golang:1.25-bookworm /usr/local/go /usr/local/go
ENV PATH=$PATH:/usr/local/go/bin:/root/go/bin:/usr/local/bin
# Install dolt for gastown
RUN curl -fsSL -o /tmp/dolt.tar.gz "https://github.com/dolthub/dolt/releases/latest/download/dolt-linux-amd64.tar.gz" && \
    tar -xzf /tmp/dolt.tar.gz -C /tmp && \
    cp /tmp/dolt-linux-amd64/bin/dolt /usr/local/bin/dolt && \
    chmod +x /usr/local/bin/dolt && \
    rm -rf /tmp/dolt.tar.gz /tmp/dolt-linux-amd64

# Install gt + bd as fallback (bind-mount from host overrides this)
RUN go install github.com/steveyegge/gastown/cmd/gt@v0.10.0 || true
RUN go install github.com/steveyegge/beads/cmd/bd@latest || true

# --- Light layers ---

# Directories for bind-mounted code/config
RUN mkdir -p /workspace /opt/scripts /opt/maintainer-skills

WORKDIR /workspace

EXPOSE 18789

# Everything below is bind-mounted from docker-compose.yml:
#   entrypoint.sh, scripts/, skills/, agent-soul.md, agent-bootstrap.md
# This means code/config changes NEVER need a docker build — just restart.

ENTRYPOINT ["/entrypoint.sh"]
