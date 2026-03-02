FROM python:3.13-slim-bookworm

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

# Claude Code + OpenClaw
RUN npm install -g @anthropic-ai/claude-code openclaw

# PyYAML for config loader
RUN pip install --no-cache-dir pyyaml

# Non-root user setup
# Home dir is 777 so any UID (via docker-compose user:) can write to it
RUN useradd -m -s /bin/bash maintainer \
    && mkdir -p /workspace \
    && chmod 777 /workspace /home/maintainer

# Copy scripts, skills, agent instructions
COPY scripts/ /opt/scripts/
COPY skills/ /opt/maintainer-skills/
COPY agent-instructions.md /opt/agent-instructions.md
RUN chmod +x /opt/scripts/*.py 2>/dev/null; \
    find /opt/maintainer-skills -name '*.sh' -exec chmod +x {} +

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace
USER maintainer

EXPOSE 18789

ENTRYPOINT ["/entrypoint.sh"]
