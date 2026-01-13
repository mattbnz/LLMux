# Stage 1: Build the web management UI
FROM node:20-slim AS web-builder

WORKDIR /app/web

# Copy web UI source
COPY web/package*.json ./
RUN npm ci

COPY web/ ./
RUN npm run build


# Stage 2: Python runtime with Tailscale
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Tailscale
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    && curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.noarmor.gpg | tee /usr/share/keyrings/tailscale-archive-keyring.gpg >/dev/null \
    && curl -fsSL https://pkgs.tailscale.com/stable/debian/bookworm.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends tailscale \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (everything except what's in .dockerignore)
COPY . .

# Copy built web UI from builder stage
COPY --from=web-builder /app/web/dist ./web/dist

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create data directory
RUN mkdir -p /data

# Environment variables
ENV PORT=8081
ENV BIND_ADDRESS=0.0.0.0
ENV LOG_LEVEL=info

# Volume for persistent data (tokens, API keys, usage DB, Tailscale state)
VOLUME ["/data"]

# The proxy port (exposed via Tailscale serve, not directly)
EXPOSE 8081

ENTRYPOINT ["/docker-entrypoint.sh"]
