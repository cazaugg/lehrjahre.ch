# Multi-stage build for lehrjahre.ch.
# Final image: python:3.14-slim running Gunicorn (API + built frontend).
#
#   docker build --target runtime -t lehrjahre .
#
# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Frontend build (build layer only, not in the final image)
# ---------------------------------------------------------------------------
FROM node:26-alpine AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Python virtualenv build (build layer only)
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS python-build
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && uv pip install --python /app/.venv/bin/python gunicorn==23.0.0

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/app/.venv/bin:$PATH
WORKDIR /app

RUN groupadd --system --gid 10001 lehrjahre \
    && useradd --system --uid 10001 --gid lehrjahre --home /app lehrjahre

COPY --from=python-build /app/.venv /app/.venv
COPY backend /app/backend
COPY data/lehrplan /app/data/lehrplan
COPY --from=frontend-build /app/dist /app/frontend/dist
COPY pyproject.toml uv.lock /app/

RUN chown -R lehrjahre:lehrjahre /app/data

USER lehrjahre:lehrjahre
EXPOSE 5000

CMD ["gunicorn", \
    "--bind", "0.0.0.0:5000", \
    "--workers", "1", \
    "--threads", "4", \
    "--worker-class", "gthread", \
    "--timeout", "120", \
    "--graceful-timeout", "30", \
    "--access-logfile", "-", \
    "--error-logfile", "-", \
    "backend.app:create_app()"]
