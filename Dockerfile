FROM ghcr.io/astral-sh/uv:0.11.9 AS uv
FROM node:25-slim AS frontend

WORKDIR /app

COPY package.json pnpm-lock.yaml postcss.config.js ./
COPY scripts ./scripts
COPY static/css/src ./static/css/src

RUN corepack enable pnpm
RUN pnpm install --frozen-lockfile
RUN pnpm build:frontend

FROM python:3.14-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
COPY --from=frontend /app/static/css/app.css ./static/css/app.css
COPY --from=frontend /app/static/vendor ./static/vendor
RUN uv sync --frozen --no-dev
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "gunicorn access_atlas.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
