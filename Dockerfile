FROM python:3.11-slim AS base

WORKDIR /app

# Run apt-get upgrade to pick up any OS-level security patches available
# in the base image, then install runtime deps.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, wheel, and jaraco.context to versions that fix known CVEs:
#   pip        < 26.1  → CVE-2026-6357, CVE-2026-1703, CVE-2025-8869
#   wheel      < 0.46.2 → CVE-2026-24049
#   jaraco.context < 6.1.0 → CVE-2026-23949 (transitive via pip)
RUN pip install --no-cache-dir --upgrade \
    "pip>=26.1" \
    "wheel>=0.46.2" \
    "jaraco.context>=6.1.0"

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
COPY README.md .
COPY frostwatch/ ./frostwatch/
# The wheel force-includes the built frontend, so it must exist before hatch runs
COPY --from=frontend-build /frontend/dist ./frontend/dist

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
