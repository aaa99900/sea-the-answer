# syntax=docker/dockerfile:1
# FastAPI backend. Build context: backend/ (see ../compose.yaml).
#   target "dev"  — dev dependencies, source bind-mounted, uvicorn --reload (compose.dev.yaml)
#   target "prod" — runtime dependencies only, non-root (compose.yaml)
FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HAEDAP_BACKUP_DIR=/data/backups
WORKDIR /app
RUN useradd --create-home --uid 10001 app && mkdir -p /data/backups /data/models /data/chroma && chown -R app:app /data
EXPOSE 8000
# Only reachable on the compose network (never published), so trust X-Forwarded-For from Next.js
# for per-client login rate limiting.
# /api/health also touches PostgreSQL, so this checks the database connection too.
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=20 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"

FROM base AS dev
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
# Source is bind-mounted over /app by compose.dev.yaml.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--proxy-headers", "--forwarded-allow-ips", "*"]

FROM base AS prod
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-default-groups
COPY api ./api
COPY tools ./tools
COPY knowledge ./knowledge
USER app
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
