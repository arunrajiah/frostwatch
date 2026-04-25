FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Build frontend ────────────────────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# ── Build Python package ──────────────────────────────────────────────────────
FROM base AS builder

RUN pip install --no-cache-dir hatch

COPY pyproject.toml .
COPY frostwatch/ ./frostwatch/

RUN hatch build -t wheel

# ── Final image ───────────────────────────────────────────────────────────────
FROM base AS final

# Copy wheel and install
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Copy built frontend into expected location
COPY --from=frontend-build /frontend/dist /app/frontend/dist

# Default config dir
RUN mkdir -p /data
ENV FROSTWATCH_DATA_DIR=/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:8000/api/sync/status || exit 1

CMD ["frostwatch", "serve", "--host", "0.0.0.0", "--port", "8000"]
