# Access Atlas

Access Atlas is a field work planning tool for teams that need to organize site visits and the jobs to complete at each site.

The first goal is to make the core planning workflow easy to use: create a trip, add site visits, assign jobs, track requirements, and give the team a clear view of planned work.

## Core Concepts

### Trip

A planned field deployment.

In the proof of concept, a trip groups the sites to visit, the jobs to complete, the people involved, and the overall planning state.

### Site Visit

A planned visit to one site during a trip.

A site visit groups the jobs planned for that site.

### Job

A specific unit of work to complete at a site.

Jobs can include a description, status, estimated duration, notes, and requirements.

### Job Template

A reusable starting point for creating common jobs.

Job templates can include a title, description, estimated duration, notes, and default requirements.

### Unassigned Job

A job that exists but has not yet been assigned to a trip.

Unassigned jobs can be reviewed and added to site visits during planning.

### Requirement

Something needed to complete a job.

Requirements may include tools, parts, cables, consumables, permissions, notes, or items already stored at the site.

## Source Of Truth

Access Atlas is designed to reference sites from an external source of truth rather than owning canonical site identity, coordinates, or addresses.

Synced site fields are read-only in Access Atlas. It owns planning-specific information such as trips, site visits, jobs, job templates, requirements, estimates, notes, and completion state.

## Proof Of Concept

The proof of concept is intentionally small so the core workflow can be tested and shaped before adding travel, access, map, or offline complexity.

The proof of concept should let users:

1. Sync read-only site references from one external site feed.
2. Create and view trips.
3. Add site visits to a trip.
4. Create reusable job templates.
5. Create and review unassigned jobs, including jobs created from templates.
6. Assign jobs to site visits.
7. Record job estimates, notes, and requirements.
8. Track simple statuses for trips, site visits, and jobs.
9. View object history so changes are attributable to users.
10. Give team leaders and managers basic visibility of planned field work.

Access Atlas should grow from this core planning workflow. Travel planning, access information, maps, tracks, and offline trip packets are ideas for later once the basics are useful.

## Development

Access Atlas is a Django application. The proof of concept runs Django locally and PostgreSQL in Docker Compose.

Prerequisites:

- Python 3.14.
- `uv`.
- Docker with Docker Compose.

Set up the project:

```bash
cp .env.example .env
docker compose up -d db
uv sync --dev
uv run python manage.py migrate
uv run python manage.py runserver
```

The app will be available at:

```text
http://127.0.0.1:8000/
```

The proof-of-concept login is passwordless and internal. Enter an email address to create/sign in as that user.

Sync dummy sites:

```bash
uv run python manage.py sync_sites
```

Run the sync command from a second terminal while the development server is running. The dummy feed is served by the app at `/dummy/site-feed.json` and requires the bearer token from `SITE_FEED_TOKEN`.

Run checks and tests:

```bash
uv run ruff check .
uv run ruff format --check .
uv run python manage.py check
uv run pytest
```

Reset the local database:

```bash
docker compose down -v
docker compose up -d db
uv run python manage.py migrate
```

VS Code users can start the Django development server with the included `Django: runserver` debug configuration.

## License

Access Atlas is licensed under the GNU Affero General Public License v3.0 or later (`AGPL-3.0-or-later`). See [LICENSE](LICENSE).
