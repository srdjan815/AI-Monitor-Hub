# Developer onboarding

## 1. Understand the boundary

Catalog owns the canonical Product. Product Attributes and Product Content build
on Catalog. Inventory references Product without duplicating it. Execution owns
durable jobs and fenced worker leases. PostgreSQL is canonical; Redis is
optional non-canonical infrastructure for shared rate limiting.

Read these before changing a business module:

- [`../architecture/module-boundaries.md`](../architecture/module-boundaries.md)
- [`../architecture/platform-foundation.md`](../architecture/platform-foundation.md)
- [`../architecture/foundation-freeze-policy.md`](../architecture/foundation-freeze-policy.md)

Do not edit applied Alembic revisions or move transaction ownership out of
services.

## 2. Prepare the repository

Requirements:

- Git;
- Windows PowerShell 5.1;
- Python 3.12.x;
- Docker Desktop with Docker Compose.

From the repository root:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.1.2
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e backend
.\.venv\Scripts\python.exe -m pip check
```

If `python` is not available or is not 3.12.x, use
[`cross-platform-python-environment.md`](cross-platform-python-environment.md).

## 3. Configure VS Code

Open the repository root rather than `backend/`. Accept the recommendations in
`.vscode/extensions.json`. The workspace selects
`.venv\Scripts\python.exe`, points analysis and pytest at `backend/`, and
configures Ruff and MyPy from `backend/pyproject.toml`.

The command palette exposes shared tasks for:

- Ruff;
- Ruff format check;
- MyPy;
- pytest;
- Alembic drift check;
- Compose startup.

## 4. Start the application

Validate configuration before starting services:

```powershell
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

The API listens on `http://localhost:8000`; Swagger is available at `/docs`
while `DOCS_ENABLED=true`. The API and worker images use digest-pinned Python,
while PostgreSQL and Redis also use pinned version/digest references.

The default Compose file is for development and bind-mounts `backend/` into
`/app`. A release deployment must execute the source baked into the validated
image rather than mount an arbitrary working tree over it.

## 5. Run quality checks

Native Windows:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend\app backend\tests
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format --check backend
Set-Location backend
..\.venv\Scripts\python.exe -m mypy app
Set-Location ..
```

Docker-authoritative database and test gates:

```powershell
docker compose exec -T api python -m pip check
docker compose exec -T api python -m pytest
docker compose exec -T api alembic heads
docker compose exec -T api alembic current
docker compose exec -T api alembic check
```

Tests use disposable, GUID-suffixed records. Do not point test commands at a
valuable database.

## 6. Work with migrations

Create a new revision only when an approved ORM/schema change requires one.
Never edit an applied migration. Before applying anything, record `heads`,
`current`, and `check`. Prove empty-to-head, populated upgrade, and relevant
downgrade/re-upgrade paths against disposable databases.

Run host Alembic commands from `backend/`:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic heads
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic check
Set-Location ..
```

## 7. Run and inspect workers

The Compose `worker` service runs the PostgreSQL-backed execution worker.
Inspect API and worker state without attaching an interactive shell:

```powershell
docker compose logs --tail 200 api
docker compose logs --tail 200 worker
docker compose ps
```

Use `docker compose logs -f api` or `docker compose logs -f worker` for live
debugging. Stop following with Ctrl+C; this does not stop the service.

## 8. Debug requests

- Start with the response `X-Request-ID` and structured API log.
- Confirm health at `GET /health`.
- Confirm an authenticated request separately from a domain mutation.
- Use route-template metrics rather than concrete entity IDs.
- Never log authorization headers, tokens, request bodies, raw prompts, or
  signing material.
- A 409 concurrency response requires reloading current state; do not blindly
  replay a stale write.

## 9. Resolve stale containers safely

Inspect before changing runtime state:

```powershell
docker compose ps
docker compose images
docker compose config --quiet
```

If source is current but dependencies are stale:

```powershell
docker compose build --no-cache api worker
docker compose up -d --force-recreate api worker
docker compose ps
```

Do not use `docker compose down -v` during ordinary development; it deletes
named database and Redis volumes. Preserve logs and database evidence before
incident recovery.

## 10. Environment variables

`.env.example` contains development-only placeholders. Copy it to ignored
`.env`, then change only local values. Never commit `.env`.

Production requires, at minimum:

- explicit allowed hosts and CORS origins;
- a strong external `AUTH_SECRET` and managed key rotation;
- non-default database credentials;
- disabled interactive documentation;
- rate limiting enabled;
- Redis shared limiting when multiple API replicas share one budget;
- trusted proxy CIDRs only for proxies that sanitize forwarded headers.

See
[`../security/production-configuration.md`](../security/production-configuration.md)
and [`../security/rate-limiting.md`](../security/rate-limiting.md).

## 11. Regenerate contract artifacts

Generate normalized OpenAPI and boundary reports from the repository root:

```powershell
.\.venv\Scripts\python.exe backend\scripts\generate_contract_reports.py
git diff -- docs\audits\openapi-normalized.json docs\audits\api-operation-matrix.json docs\audits\request-boundary-inventory.json
```

Review generated changes; do not accept contract drift merely because generation
succeeded.

## 12. Prepare a release

Follow [`release-procedure.md`](release-procedure.md). A release requires
classification and secret review, all mandatory gates, explicit staging,
professional commits, an annotated tag, and clean-clone reproduction. Do not
push unless separately authorized.
