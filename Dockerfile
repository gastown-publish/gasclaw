# Multi-platform build for AMD64 and ARM64 (Apple Silicon)
# Build with: docker buildx build --platform linux/amd64,linux/arm64 -t gasclaw .
FROM --platform=$TARGETPLATFORM python:3.13-slim-bookworm

# Build arguments for multi-platform support
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git tmux ca-certificates gnupg \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22 (architecture-specific)
RUN case "${TARGETARCH}" in \
        amd64) NODE_ARCH=x64 ;; \
        arm64) NODE_ARCH=arm64 ;; \
        *) NODE_ARCH=x64 ;; \
    esac && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Go 1.24 (multi-platform: amd64 or arm64)
RUN curl -fsSL https://go.dev/dl/go1.24.2.linux-${TARGETARCH}.tar.gz | tar -C /usr/local -xzf -
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"

# Dolt (multi-platform - install appropriate binary)
RUN case "${TARGETARCH}" in \
        amd64) DOLT_ARCH=amd64 ;; \
        arm64) DOLT_ARCH=arm64 ;; \
        *) DOLT_ARCH=amd64 ;; \
    esac && \
    curl -fsSL https://github.com/dolthub/dolt/releases/latest/download/dolt-linux-${DOLT_ARCH}.tar.gz | \
    tar -C /usr/local/bin -xzf - --strip-components=1 dolt-linux-${DOLT_ARCH}/bin/dolt

# Claude Code
RUN npm install -g @anthropic-ai/claude-code

# OpenClaw
RUN npm install -g openclaw

# KimiGas (kimi-cli)
RUN pip install --no-cache-dir kimi-cli

# Gastown (gt)
RUN pip install --no-cache-dir gastown

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
