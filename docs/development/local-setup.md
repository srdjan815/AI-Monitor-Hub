# Local development setup

This is the concise setup entry point. The complete workflow, including
debugging and stale-container recovery, is in
[`../operations/developer-onboarding.md`](../operations/developer-onboarding.md).

## Requirements

- Windows PowerShell 5.1
- Python 3.12.x
- Docker Desktop with Docker Compose
- Git

Open PowerShell in the repository root. The canonical host environment is
`.venv`; do not create `venv`, `.venv-1`, or another environment under
`backend/`. Docker installs the same exact lock independently and never uses the
host environment.

## Create the environment

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.1.2
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e backend
.\.venv\Scripts\python.exe -m pip check
```

If `python` does not resolve to Python 3.12, follow
[`../operations/cross-platform-python-environment.md`](../operations/cross-platform-python-environment.md).

`backend/pyproject.toml` declares supported dependency ranges.
`backend/requirements.lock` records the complete exact tested environment,
including build, runtime, development, test, typing, formatting, and advisory
tools.

## Configuration and Docker

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

The API runs on port 8000. PostgreSQL and Redis use internal Compose networking
and persistent named volumes. PostgreSQL remains canonical for every domain.
Redis is optional non-canonical infrastructure for the shared multi-instance
rate limiter; the in-memory limiter remains available for local development.

### Supplier source credentials in development

Supplier Source credentials are intentionally stored only in the API process
memory during development. The database stores an opaque `secret:runtime/...`
reference, never the credential value. Restarting or replacing the API
container clears the in-memory values, so every affected Source Connection must
receive its credentials again and pass Probe again. The Source API exposes
availability only as a boolean; responses, UI messages and logs must never
expose the opaque reference or credential values. Production fails closed until
an approved external secret provider is configured.

## Quality and tests

```powershell
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
Set-Location backend
..\.venv\Scripts\python.exe -m mypy app
..\.venv\Scripts\python.exe -m pytest
Set-Location ..
```

The root `.env` uses Compose service names such as `db`, which do not resolve
from native Windows. Use the host environment for static and database-free
tests; run the complete PostgreSQL-backed suite inside Docker:

```powershell
docker compose exec -T api python -m pytest
```

## Alembic

Run Alembic from `backend` so it finds `alembic.ini`:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic heads
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic check
Set-Location ..
```

Do not edit an applied revision or run an upgrade against an unknown database.
Use disposable databases for upgrade/downgrade proof.

## Architecture boundary

Catalog is the canonical product master. Inventory is a frozen optional
downstream module and is not a prerequisite for product creation or future
Supplier Feed, Import, Matching, Pricing, AI, Media, or Publishing work. See
[`../architecture/module-boundaries.md`](../architecture/module-boundaries.md).
