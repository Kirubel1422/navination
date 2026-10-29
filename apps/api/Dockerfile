# NaviNation API image: FastAPI + uv-locked dependencies. Build context: apps/api
FROM python:3.13.18-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Dependencies first (cached layer), exactly as locked, without dev tools.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh \
    && useradd --system --uid 10001 --home /app navination \
    && mkdir -p /app/data \
    && chown -R navination /app/data

USER navination
ENV DATABASE_URL=sqlite:////app/data/navination.db \
    APP_ENV=production
VOLUME ["/app/data"]
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2).status == 200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
