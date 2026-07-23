# AI Monitor Hub

AI Monitor Hub imports and normalizes supplier product data, matches supplier
items to the internal Catalog, supports product enrichment and pricing, and
publishes selected data to an external ERP and web shop.

AI Monitor Hub is not an ERP. Procurement, warehouse documents, sales,
invoicing, and accounting remain responsibilities of the external ERP.

## Current baseline

The implemented backend contains:

- Catalog categories, products, attribute definitions, and category attributes;
- a PostgreSQL-backed execution/job foundation;
- frozen optional Inventory, Movement, and Reservation APIs.

Supplier Feed, Import, Matching, Pricing, AI, Scraper, Media, and Publishing
are future modules and are not implemented yet.

## Repository layout

```text
backend/                 FastAPI application, Alembic, and tests
docs/architecture/       enforced module boundaries
docs/development/        canonical development instructions
docs/audits/             repository health records
docker-compose.yml       API, worker, PostgreSQL, and Redis
.env.example             local configuration template
```

The canonical host virtual environment is `.venv`. Docker is independent from
the host environment and bind-mounts `backend/` into `/app`.

## Quick start

```powershell
Copy-Item .env.example .env
C:\Users\PC\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
docker compose up -d
```

Swagger is available at `http://localhost:8000/docs`.

Canonical setup, validation, and migration commands are documented in
[docs/development/local-setup.md](docs/development/local-setup.md). Architecture
rules are documented in
[docs/architecture/module-boundaries.md](docs/architecture/module-boundaries.md).
