# ── Stage 1: Build frontend ───────────────────────────────────────────────────
FROM --platform=$BUILDPLATFORM node:22.23.4-alpine AS frontend-builder

# eMudhra: refresh both the CA sources and the generated bundle.
RUN apk add --no-cache --upgrade ca-certificates ca-certificates-bundle \
    && update-ca-certificates
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# ── Stage 2: Runtime (Python + Node + supervisord) ────────────────────────────
FROM python:3.12-slim

# eMudhra: refresh the OS trust store for this security update.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}
ENV TZ=UTC

# Install Node.js 22, supervisord, gosu, curl and tzdata
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    curl \
    gosu \
    supervisor \
    tzdata \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && dpkg --compare-versions "$(node --version | cut -c2-)" ge 22.23.4 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# ── Backend ───────────────────────────────────────────────────────────────────
WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY backend/ .

# ── Frontend ──────────────────────────────────────────────────────────────────
WORKDIR /app/frontend

COPY --from=frontend-builder /app/frontend/dist ./dist
COPY --from=frontend-builder /app/frontend/node_modules ./node_modules
COPY --from=frontend-builder /app/frontend/package.json ./

# ── Entrypoint & supervisor config ────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
COPY supervisord.conf /etc/supervisor/conf.d/scrob.conf
RUN chmod +x /entrypoint.sh

EXPOSE 7330

# Requires Docker Engine 25+ for --start-interval
HEALTHCHECK --interval=2m --timeout=2s --start-period=20s --start-interval=5s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${BACKEND_PORT:-7331}/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
