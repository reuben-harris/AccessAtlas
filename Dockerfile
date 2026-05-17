FROM ghcr.io/astral-sh/uv:0.11.14 AS uv
FROM node:26-slim AS frontend

WORKDIR /app

COPY package.json pnpm-lock.yaml postcss.config.js ./
COPY scripts ./scripts
COPY static/css/src ./static/css/src

RUN PNPM_VERSION="$(node -p "require('./package.json').packageManager.split('@')[1]")" \
    && npm install -g "pnpm@${PNPM_VERSION}"
RUN pnpm install --frozen-lockfile
RUN pnpm build:frontend

FROM python:3.14-slim AS docs

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock zensical.toml ./
RUN uv sync --frozen --dev --no-install-project

COPY docs ./docs
COPY access_atlas/__init__.py ./access_atlas/__init__.py
COPY access_atlas/core/__init__.py ./access_atlas/core/__init__.py
COPY access_atlas/core/markdown_extensions ./access_atlas/core/markdown_extensions
RUN PYTHONPATH=/app uv run zensical build --strict

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
COPY --from=docs /app/static/docs ./static/docs
RUN uv sync --frozen --no-dev
RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["sh", "-c", "gunicorn access_atlas.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
