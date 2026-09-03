# AI Monitor Hub

AI Monitor Hub imports and normalizes supplier product data, matches supplier
items to the internal Catalog, supports product enrichment and pricing, and
publishes selected data to an external ERP and web shop.

AI Monitor Hub is not an ERP. Procurement, warehouse documents, sales,
invoicing, and accounting remain responsibilities of the external ERP.

## Current baseline

The implemented backend contains:

- Catalog categories, products, attribute definitions, and category attributes;
- the Product Attribute platform, including normalized values, formulas,
  templates, families, dependencies, prompts, and resolved projections;
- the Product Content platform, including revisions, templates, quality
  scoring, references, and approval-oriented lifecycle operations;
- Inventory, Movement, and Reservation APIs;
- a fenced PostgreSQL-backed execution/job worker foundation;
- authentication, request boundaries, signed cursor pagination, rate limiting,
  structured logging, and Prometheus-compatible metrics.

Supplier Feed, Import, Matching, Pricing, AI, Scraper, Media, and Publishing
are future modules and are not implemented yet.

## Repository layout

```text
backend/                 FastAPI application, Alembic, and tests
docs/architecture/       enforced module boundaries
docs/development/        concise local setup entry point
docs/operations/         onboarding, release, and runbooks
docs/security/           security and deployment contracts
docs/audits/             repository health records
docker-compose.yml       API, worker, PostgreSQL, and Redis
.env.example             local configuration template
```

The canonical Windows virtual environment is the ignored, repository-local
`.venv`. The checked Docker image uses a digest-pinned Python 3.12 base and the
same exact dependency lock. The default Compose file is a development workflow:
it bind-mounts `backend/` into `/app`. A release image must be built from the
validated commit and run without replacing its application source.

## Quick start

Run these commands from the repository root in Windows PowerShell 5.1:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pip==26.1.2
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e backend
docker compose config --quiet
docker compose up --build -d
```

Swagger is available at `http://localhost:8000/docs`.

If `python` is not on `PATH`, use the interpreter-discovery instructions in
[the cross-platform environment guide](docs/operations/cross-platform-python-environment.md).
The complete workflow is in
[developer onboarding](docs/operations/developer-onboarding.md), while the
short setup entry point remains at
[docs/development/local-setup.md](docs/development/local-setup.md). Architecture
rules are in
[docs/architecture/module-boundaries.md](docs/architecture/module-boundaries.md).

## Destructive integration tests

The repository includes a separately fenced, disposable test system. It is
**test-only and must not be used for development or real data**. Run it only via
`scripts/Invoke-IsolatedTestSuite.ps1`; see
[the isolated test environment runbook](docs/operations/isolated-test-environment.md).
