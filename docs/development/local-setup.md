# Local development setup

## Requirements

- Windows PowerShell 5.1
- Python 3.12
- Docker Desktop with Docker Compose
- Git

The canonical host environment is `C:\AI-Monitor-Hub\.venv`. Do not create
`venv`, `.venv-1`, or an environment below `backend/`. Docker installs its own
dependencies and does not use the host environment.

## Create the environment

From `C:\AI-Monitor-Hub`:

```powershell
C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
```

`backend/pyproject.toml` is the single dependency source of truth. Runtime
dependencies are under `[project.dependencies]`; developer tools are under
`[project.optional-dependencies].dev`.

## Configuration and Docker

```powershell
Copy-Item .env.example .env
docker compose config --quiet
docker compose up -d
docker compose ps
```

The API runs on port 8000. PostgreSQL and Redis use internal Compose networking
and persistent named volumes. The execution worker polls PostgreSQL; Redis is
reserved infrastructure and is not currently used by application code.

## Quality and tests

```powershell
.\.venv\Scripts\ruff.exe check backend
.\.venv\Scripts\python.exe -m pytest backend\tests
```

Integration tests expect the Compose API and PostgreSQL services to be running.
They use GUID-suffixed disposable records.

## Alembic

Run Alembic from `backend` so it finds `alembic.ini`:

```powershell
Set-Location backend
..\.venv\Scripts\alembic.exe heads
..\.venv\Scripts\alembic.exe current
..\.venv\Scripts\alembic.exe check
Set-Location ..
```

Do not edit historical migrations. Do not run upgrades against an unknown
database.

## Architecture boundary

Catalog is the canonical product master. Inventory is a frozen optional
downstream module and is not a prerequisite for product creation or future
Supplier Feed, Import, Matching, Pricing, AI, Media, or Publishing work. See
[`../architecture/module-boundaries.md`](../architecture/module-boundaries.md).
