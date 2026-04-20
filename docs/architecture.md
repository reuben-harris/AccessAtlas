# Architecture

Access Atlas is a Django server-rendered application using PostgreSQL as the primary database, Tabler for layout, and HTMX for focused partial updates.

The proof of concept should stay deliberately small. The first implementation should focus on the core planning workflow before adding map, travel, access, offline, or spatial features.

## Direction

The application should use a server-rendered architecture by default.

- Django owns routing, authentication, permissions, domain models, validation, templates, and business rules.
- PostgreSQL stores application data.
- Tabler provides the main layout and UI component foundation.
- HTMX provides partial page updates where they improve the object workflow.
- The UI should follow a NetBox-style layout: persistent left navigation, top search, and consistent object list/detail/edit pages in the main content area.
- The proof of concept should support light and dark mode using Tabler's theme support.

## Proof Of Concept Frontend

The proof of concept does not need a heavy frontend toolchain.

Start with:

- Django templates.
- Tabler assets.
- Light/dark theme toggle.
- HTMX.
- Minimal plain JavaScript only where unavoidable.

Do not introduce React or a single-page application by default.

Vite, TypeScript, Stimulus, and Biome are possible later additions once the project needs structured browser-side code. They do not need to be part of the first scaffold unless an early feature requires them.

## Database

PostgreSQL is the default database.

The proof-of-concept domain model is relational and includes trips, site visits, jobs, requirements, and external site references. PostgreSQL is a good fit for those relationships and has a straightforward deployment path to managed services such as AWS RDS.

PostGIS is deferred. It should be considered later when Access Atlas adds spatial storage or querying for maps, trip locations, road ends, tracks, or map filtering.

## Django Scaffold Requirements

When the Django project is scaffolded, include the project tooling from the start.

- Use Python 3.14, the latest stable Python feature series for the proof of concept.
- Use Django 6.0, which supports Python 3.14.
- Use `uv` for local dependency management and environment setup.
- Include a `pyproject.toml` for project metadata, Python version requirements, runtime dependencies, and development dependencies.
- Include a `.python-version` file so local tooling and GitHub Actions resolve the intended Python version consistently.
- Include VS Code debug configuration for running and debugging the Django development server.
- Include GitHub Actions CI for lint and test checks.
- Include a GitHub Actions container workflow for publishing deployable images to GitHub Container Registry.
- Include Dependabot configuration for Python dependencies and GitHub Actions updates.

Recommended scaffold files:

```text
pyproject.toml
.python-version
.vscode/
  launch.json
  settings.json
.github/
  workflows/
    ci.yml
    container.yml
  dependabot.yml
```

The initial CI workflow should use current official GitHub Actions:

- `actions/checkout@v6`
- `actions/setup-python@v6`

The CI workflow should explicitly set the Python version rather than relying on the runner default.

The proof-of-concept CI should stay simple:

```text
checkout
set up Python
install project and development dependencies
run formatting/linting checks if configured
run Django checks
run tests
```

Dependabot should check:

- Python dependencies from `pyproject.toml`.
- GitHub Actions versions from `.github/workflows`.

The container workflow should build a deployable image and publish it to GitHub Container Registry under the project repository.

Recommended Django app structure:

```text
access_atlas/
  project settings and URL configuration

  core/
    shared templates, layout, navigation, dashboard, and common utilities

  accounts/
    custom user model and authentication integration points

  sites/
    read-only synced site references and site feed sync

  jobs/
    jobs, job templates, requirements, and template requirements

  trips/
    trips, site visits, and job assignment workflow
```

Use a minimal custom user model from the start, even if the proof of concept uses Django's built-in login screens initially. This keeps the project ready for Microsoft organization SSO later and avoids changing Django's user model after migrations exist.

For the proof of concept, users should identify themselves by email without password authentication. The app is intended to be hosted internally while the workflow is being tested. Logged-in users can do everything in the application. Microsoft organization SSO can replace the proof-of-concept login later.

The proof of concept should include object history/auditing in the NetBox style: users should be able to see what changed, when it changed, and which logged-in user made the change. Use `django-simple-history` for this unless a concrete incompatibility appears.

The site feed URL and token should be configured through environment variables, not through a settings UI. The dummy site feed endpoint should still require the configured bearer token so the real sync path is exercised.

For local development, run Django locally and PostgreSQL in Docker Compose. The proof of concept should include a small Django-served dummy site feed endpoint so the site sync path can be exercised over HTTP before a real external adapter exists.

## Deferred Architecture

These architecture pieces are intentionally deferred. They are ideas to revisit only when the product needs them:

- Leaflet map views.
- Vite-managed TypeScript.
- Stimulus controllers.
- Biome frontend linting and formatting.
- PostGIS-backed spatial data.
- KML import/export.
- GeoJSON import/export.
- Offline trip packets.
- Native mobile apps.

If map features are introduced, Leaflet is the current preferred first mapping library. If structured browser-side code is introduced, revisit Vite, TypeScript, Stimulus, and Biome rather than drifting into unstructured standalone JavaScript.

## Deployment Shape

The intended deployment shape is simple:

```text
Django web application
  connects to PostgreSQL
  serves server-rendered pages
```

In AWS, the web application should be deployable as a container or conventional web service that points at an RDS PostgreSQL instance.

## Repository

The intended GitHub remote is:

```text
git@github.com:reuben-harris/AccessAtlas.git
```
