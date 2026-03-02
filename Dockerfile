FROM python:3.13-slim-bookworm

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git tmux ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Go 1.24 (multi-platform: amd64 or arm64)
ARG TARGETARCH
RUN curl -fsSL https://go.dev/dl/go1.24.1.linux-${TARGETARCH}.tar.gz | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"

# Dolt
RUN curl -fsSL https://github.com/dolthub/dolt/releases/latest/download/install.sh | bash

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# OpenClaw
RUN npm install -g openclaw || true

# KimiGas (kimi-cli)
RUN pip install --no-cache-dir kimi-cli || true

# Gastown (gt)
RUN pip install --no-cache-dir gastown || true

# Install gasclaw
WORKDIR /opt/gasclaw
COPY pyproject.toml .
COPY src/ src/
COPY skills/ skills/
RUN pip install --no-cache-dir .

# Create directories
RUN mkdir -p /workspace/gt /project

# Volume mount point
VOLUME /project

# OpenClaw gateway port
EXPOSE 18789

# Entrypoint
ENTRYPOINT ["gasclaw"]
CMD ["start"]
