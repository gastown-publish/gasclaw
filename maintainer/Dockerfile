FROM python:3.13-slim-bookworm

# System deps + Node.js 22
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git tmux ca-certificates gnupg jq \
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

# Claude Code + OpenClaw
RUN npm install -g @anthropic-ai/claude-code openclaw

# Non-root user (Claude Code refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash maintainer \
    && mkdir -p /workspace && chown maintainer:maintainer /workspace

# Working directory
WORKDIR /workspace

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER maintainer
ENTRYPOINT ["/entrypoint.sh"]
