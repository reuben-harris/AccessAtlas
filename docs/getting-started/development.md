# Development

Local development normally runs Django directly and PostgreSQL through Docker
Compose.

## Prerequisites

- Python 3.14
- `uv`
- `pnpm`
- Docker with Docker Compose

## Setup

```bash
cp .env.example .env
docker compose up -d db
uv sync --dev
pnpm install
pnpm build:frontend
uv run python manage.py migrate
uv run python manage.py runserver
```

The app is available at `http://127.0.0.1:8000/`.

## Useful Commands

```bash
uv run python manage.py check
uv run pytest
uv run ruff check .
uv run ruff format --check .
PYTHONPATH=. uv run zensical build --strict
pnpm lint:docs
pnpm lint:frontend
pnpm build:frontend
```

## Documentation

Documentation source files live under `docs/`. The generated static site is
written to `static/docs/`, which is ignored by git and rebuilt in CI and Docker.

Use GitHub-style alerts for callouts:

```markdown
> [!WARNING]
> Keep synced site fields read-only in Access Atlas.
```
