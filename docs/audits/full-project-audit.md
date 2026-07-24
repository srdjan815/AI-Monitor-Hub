# Full project audit

Audit date: 2026-07-23
Repository: `<repository-root>`
Branch: `feature/product-core`

## 1. Executive summary

Confirmed from code: the runnable system is a FastAPI backend with PostgreSQL,
a database-polled execution worker, Catalog CRUD, and the frozen optional
Inventory subsystem. The active source root is `backend/app`; Docker Compose
bind-mounts `./backend` to `/app`. There is no implemented frontend and there
are no implemented Supplier Feed, Import, Matching, Pricing, AI, Scraper,
Media, Publishing, or ERP Sync modules.

Catalog is usable for categories, products, attribute definitions, category
attribute assignment, and an Attribute Type API façade. It is not yet a
complete product-information model: product content, translations, product
attribute values, supplier offers, prices, media, provenance, approval, and
history are absent.

The repository is operational but not in a releasable Git state. Four
migrations, the whole Inventory package, multiple test suites, and the module
boundary document are untracked. Thirteen tracked files contain substantial
unstaged changes. A malformed root artifact remains untracked. Stale compiled
artifacts preserve names from an interrupted alternative Catalog architecture.

Runtime validation is healthy: syntax compilation, mapper configuration,
Alembic head/current/drift checks, and all 29 tests pass. Full Ruff fails only
on two unused imports in the tracked empty initial migration.

## 2. Git state

### Branch and history

- Current branch: `feature/product-core`.
- Tracking state: one commit ahead of `origin/feature/product-core`.
- HEAD: `760566a Refactor catalog routers and schemas into package structure`.
- Recent relevant history:
  - `0365cca Add category tree API`
  - `ca7a606 Merge branch 'feature/product-admin-api' into develop`
  - `ae6eef1 Improve category validation and deactivation`
  - `253d2de chore: remove temporary product core copy`
  - `27a8ec4 feat: add product core foundation`
  - `a6990d7 feat: configure alembic and initial database migration`

### Working tree

No staged changes, tracked deletions, renames, or merge-conflict markers were
found.

Tracked unstaged files:

- `backend/alembic/env.py`
- `backend/app/api/router.py`
- `backend/app/core/logging.py`
- `backend/app/modules/catalog/models.py`
- `backend/app/modules/catalog/repository.py`
- `backend/app/modules/catalog/router.py`
- `backend/app/modules/catalog/routers/attribute_types.py`
- `backend/app/modules/catalog/schemas/__init__.py`
- `backend/app/modules/catalog/schemas/categories.py`
- `backend/app/modules/catalog/schemas/products.py`
- `backend/app/modules/catalog/service.py`
- `backend/app/modules/execution/repository.py`
- `backend/tests/test_health.py`

Tracked diff size before this report: 709 insertions and 124 deletions across
13 files. The changes implement or stabilize active Catalog, logging,
execution, router, and metadata behavior; they are not a single isolated
change set.

Important untracked source:

- `backend/alembic/versions/eb5f2829e72e_add_products_table.py`
- `backend/alembic/versions/f1a2b3c4d5e6_inventory_foundation.py`
- `backend/alembic/versions/b2c3d4e5f6a7_inventory_movements.py`
- `backend/alembic/versions/c3d4e5f6a7b8_inventory_reservations.py`
- `backend/app/modules/inventory/`
- `backend/tests/test_catalog_crud.py`
- `backend/tests/test_catalog_transactions.py`
- `backend/tests/test_inventory_crud.py`
- `backend/tests/test_inventory_movements.py`
- `backend/tests/test_inventory_reservations.py`
- `backend/tests/test_inventory_transactions.py`
- `backend/tests/test_module_boundaries.py`
- `docs/architecture/module-boundaries.md`

These files are active, imported, applied, or collected. They must not be
treated as disposable simply because Git reports them as untracked.

## 3. Repository structure

```text
<repository-root>
├── backend/                    active Python/FastAPI application
│   ├── alembic/versions/       seven-revision migration chain
│   ├── app/
│   │   ├── api/                central API router and health route
│   │   ├── core/               settings and logging
│   │   ├── db/                 SQLAlchemy engine/session/base/mixins
│   │   └── modules/
│   │       ├── catalog/        registered, modeled, API, tests
│   │       ├── execution/      registered jobs API and worker
│   │       └── inventory/      registered frozen optional module
│   └── tests/                  collected unit/integration/transaction tests
├── docs/                       design documents and architecture boundary
├── docker-compose.yml          API, worker, PostgreSQL, Redis
├── .env.example                development configuration template
├── app/, tests/                empty root remnants
├── config/, dagster/, data/    empty root remnants
├── docker/                     empty root remnant
├── AI-Cenovnici/               empty duplicated scaffold
└── backend_product_core_v1/    ignored compiled/cache snapshot
```

There is no frontend source, `scripts` directory, supplier implementation,
ingestion implementation, scraper implementation, AI implementation, pricing
implementation, or media implementation. References to those capabilities are
documentation only, primarily under `docs/`.

### Module map

| Module | Registered | API | Models/tables | Tests | State |
|---|---:|---:|---:|---:|---|
| `backend/app/modules/catalog` | yes | yes | 4 tables | yes | active, partial domain |
| `backend/app/modules/execution` | yes | yes | 3 tables | unit only | generic foundation |
| `backend/app/modules/inventory` | yes | yes | 4 tables | yes | complete but frozen |
| Supplier Feed | no | no | no | no | absent |
| Import/Normalization | no | no | no | no | absent |
| Product Matching | no | no | no | no | absent |
| Pricing | no | no | no | no | absent |
| AI Enrichment | no | no | no | no | absent |
| Scraper | no | no | no | no | absent |
| Media | no | no | no | no | absent |
| Publishing/ERP Sync | no | no | no | no | absent |
| Frontend | no | no | no | no | absent |

## 4. Duplicate and suspicious files/folders

| Path | Tracking/reference | Assessment | Removal risk/recommendation |
|---|---|---|---|
| `s -ExecutionPolicy RemoteSigned) ; (& cAI-Monitor-Hub.venvScriptsActivate.ps1)` | untracked, no code references, 3,347 bytes | malformed accidental PowerShell artifact | likely safe to remove after manual content confirmation; do not execute |
| `backend_product_core_v1/` | ignored by `.gitignore`, no source `.py` files remain; caches, bytecode, egg-info only | obsolete generated snapshot from earlier product-core work | low source risk, but verify no external process uses it before removal |
| `backend/app/modules/catalog/schemas.py` and `backend/app/modules/catalog/schemas/` | both tracked; imports resolve to the package; tests exercise package exports | duplicate schema concept from package migration | `schemas/` is active and must remain; remove legacy `schemas.py` only in an approved cleanup after import verification |
| `backend/app/modules/catalog/models/` | only ignored `__pycache__/attribute_type...pyc`; active code is `models.py` | stale compiled evidence of abandoned package architecture | source-independent cache; safe cleanup candidate, not active code |
| `backend/app/modules/catalog/repository/` | only stale bytecode; active code is `repository.py` | obsolete package remnant | safe cleanup candidate after confirmation |
| `backend/app/modules/catalog/services/` | only stale bytecode for split services; active code is `service.py` | obsolete interrupted refactor remnant | safe cleanup candidate after confirmation |
| `backend/app/modules/catalog/tests/` | only stale bytecode; collected tests are under `backend/tests` | obsolete test remnant | safe cleanup candidate after confirmation |
| `backend/app/modules/catalog/routers/__pycache__/attribute_type_router...` and `product_router...` | bytecode only; active routers are `attribute_types.py` and `products.py` | obsolete router names | safe cache cleanup candidate |
| root `app/`, `tests/`, `config/`, `dagster/`, `data/`, `docker/` | empty and untracked | unused scaffold remnants | low risk, but external tooling cannot be ruled out from repository evidence |
| `AI-Cenovnici/` and its child scaffold folders | empty and untracked | duplicated abandoned project scaffold | low risk; verify external tooling before removal |
| `.venv/` and `.venv-1/` | ignored; two full environments | duplicate local environments | not application source; retain the working `.venv` until toolchain is repaired/confirmed |
| `backend/ai_cenovnici_api.egg-info/`, caches, and `__pycache__` | ignored generated output | build/runtime artifacts | regenerable, but no cleanup was performed |
| root design Markdown and `docs/` | tracked; root files are legacy high-level designs, numbered docs are broader planned architecture | split documentation layout, not exact duplicates | consolidate only with explicit documentation migration |

No filename pairs differing only by capitalization were found. No duplicate
migration revision IDs or multiple Alembic heads were found. Common filenames
such as `models.py`, `router.py`, and `__init__.py` across distinct modules are
intentional rather than duplicates.

## 5. Catalog status

### Categories

Confirmed model: `Category` in
`backend/app/modules/catalog/models.py`.

Implemented fields and behavior:

- UUID `id`; `name`; unique `code`; nullable self-referencing `parent_id`.
- `position`, `is_active`, `version`, `created_at`, and `updated_at`.
- Parent/child ORM relationships.
- Unique `(parent_id, name)` constraint and hierarchy/order indexes.
- Stable server-side code generation and duplicate validation in
  `backend/app/modules/catalog/service.py`.
- Parent existence, inactive parent, self-parent, and descendant-cycle checks.
- Global attributes are linked when a category is created.
- CRUD, tree, active/parent filtering, ordering, and pagination routes in
  `backend/app/modules/catalog/router.py`.

Missing:

- slug distinct from code, description, SEO fields, category content,
  category templates, translations, and source/provenance.
- Explicit category-attribute link/unlink endpoints. Category-scoped links are
  created as a side effect of attribute creation; only list and reorder are
  exposed afterward.

Tests: CRUD and transaction coverage in
`backend/tests/test_catalog_crud.py`,
`backend/tests/test_catalog_transactions.py`, and unit validation in
`backend/tests/test_catalog_unit.py`.

### Products

Confirmed model: `Product` in
`backend/app/modules/catalog/models.py`.

Implemented:

- UUID, required category, name, immutable-through-API unique internal code.
- Unique nullable `sku` and `ean`; nullable `mpn`.
- Text `brand` and `manufacturer`.
- Free-form string `status`, soft-delete `is_active`, timestamps, version.
- POST/GET/list/PATCH/DELETE-soft routes under `/api/v1/products`.
- Duplicate code/SKU/EAN validation with database constraints as backstop.
- Active filtering and pagination.

Gaps:

- No distinct product model field; MPN exists but model designation does not.
- No GTIN normalization/check-digit validation or barcode type.
- `sku` is global and unique, not supplier-specific; there is no supplier SKU
  mapping.
- Brand/manufacturer are strings, not canonical related entities.
- Status is free-form, not an application or database enum.
- No source tracking, approval state, audit history, merge/duplicate handling,
  publication state, or external-system identifiers.
- No short/long description, specification, SEO title/description, keywords,
  media, translations, or product attribute values.
- List filters only `active_only`; there is no category, identifier, brand,
  manufacturer, status, or search filter.

Tests: Product CRUD, duplicate values, soft deletion, rollback, and Inventory
independence are covered under `backend/tests`.

## 6. Category and attribute status

`AttributeDefinition` is the only attribute-type entity. “Attribute Types” is
an API façade over it; there is no `AttributeType` table. This is intentional
in the active architecture.

Supported application data types in
`backend/app/modules/catalog/enums.py`:

- `TEXT`, `LONG_TEXT`, `INTEGER`, `DECIMAL`, `BOOLEAN`, `URL`, `SELECT`,
  `MULTISELECT`, and `JSON`.

Implemented definition fields:

- name, code, global/category scope, data type, unit, description, AI prompt,
  example value, JSON validation rules, API name, required/visible/filterable/
  searchable/multiple flags, active state, version, and timestamps.

`CategoryAttribute` implements category assignment, group, position, required/
visible/prompt/validation overrides, active state, version, and timestamps.

Gaps:

- No product attribute value model or table.
- No option/allowed-value entity for SELECT/MULTISELECT; only unstructured
  `validation_rules` JSON can carry such data.
- No explicit RANGE or DATE type.
- No normalization service for attribute values.
- `/attributes` provides create/list/update but no GET-by-ID or delete/
  deactivate route.
- No direct link/unlink/reactivate endpoint for existing category assignments.
- “Attribute Types” and “Attributes” expose the same rows through overlapping
  APIs, creating semantic duplication and the possibility that Attribute Type
  calls affect ordinary AttributeDefinition rows.

## 7. Product-content and description status

Product content is absent from current models and migrations. Product has no
description field and there is no separate content entity.

The database cannot distinguish:

- short, long, technical, marketing, or SEO content;
- Serbian and English versions;
- raw imported, manufacturer, AI-generated, human-edited, or approved text;
- active content from prior versions;
- source citations or content audit history.

The planned concepts in `docs/02_database.md`, `docs/03_admin_panel.md`, and
`docs/04_ai_engine.md` are documentation, not executable support.

## 8. Supplier price-list import status

No supplier, supplier feed, supplier item, supplier offer, price-list, upload,
mapping, import batch, import row, import error, staging, or source-file model,
service, router, worker handler, or test exists.

The generic execution foundation in
`backend/app/modules/execution/` can enqueue and process jobs, but its only
handlers are `system.health_echo` and `test`; it does not parse or persist
supplier data.

End-to-end flow:

| Step | Status | Evidence |
|---|---|---|
| Receive/upload price list | ABSENT | no upload route or storage |
| Identify supplier | ABSENT | no Supplier entity |
| Parse XML/CSV/XLSX/JSON/API/PDF | ABSENT | no parser dependencies or code |
| Map columns/fields | ABSENT | no mapping model/service |
| Normalize values | ABSENT | Catalog `stable_code` is not feed normalization |
| Preserve raw source | ABSENT | no source file/snapshot/raw row |
| Store normalized supplier item | ABSENT | no supplier item table |
| Validate identifiers/prices/tax/availability | ABSENT | no feed schemas |
| Detect changed rows | ABSENT | no hashes or row versioning |
| Idempotent retry | ABSENT | generic jobs have an idempotency key only |
| Errors/statistics/history | ABSENT | job errors are not import-row errors |
| Hand off to matching | ABSENT | no matching pipeline |

Supplier availability is not represented anywhere, so it is not currently
confused with internal Inventory. Future implementation must preserve that
separation.

## 9. Product matching status

There is no matching pipeline. Catalog CRUD can manually create products and
enforces exact uniqueness for internal code, SKU, and EAN, but this is not
supplier-item matching.

Absent:

- exact EAN/GTIN, MPN, manufacturer+model, supplier SKU, fuzzy name, normalized
  brand, category-assisted, or AI matching;
- match candidates, confidence scores/thresholds, automatic/manual decisions,
  rejection, rematching, or decision history;
- persistent supplier-item-to-product mapping.

The database does not support one internal product with offers from multiple
suppliers or stable supplier item identity across feed changes. It also cannot
stage a proposed new product for manual review.

## 10. Pricing status

No executable pricing model, schema, service, endpoint, utility, test,
frontend, spreadsheet, or workflow exists. `docs/06_pricing_engine.md` and
other design documents are plans only.

The system cannot calculate supplier net cost, additional costs, margin/
markup, VAT, retail price, rounding, promotions, or price history. It does not
model or distinguish discount, rebate, margin, markup, or VAT.

Inventory movements contain quantities only and are correctly not used as a
purchase-price source.

## 11. AI status

There is no AI provider package, model selection, prompt store, OpenAI/Ollama
client, embedding/RAG/vector integration, structured-output validation,
confidence scoring, token accounting, retry policy, approval workflow, or
Catalog integration.

`AttributeDefinition.ai_prompt` and `ai_prompt_override` are passive text
fields, not an AI engine. `docs/04_ai_engine.md` describes intended providers
and agents but none are implemented.

The database cannot distinguish raw, manufacturer, AI-generated, edited, or
approved content.

## 12. Scraper status

No scraper code or dependencies were found. Playwright, Selenium,
BeautifulSoup, Scrapy, HTTP fetching, JSON-LD extraction, specification/media
extraction, source snapshots, hashes, rate limits, retries, anti-bot handling,
and manufacturer adapters are absent.

No manufacturer URL-to-review workflow is currently possible.

## 13. Media status

No media model, table, route, filesystem/object-storage configuration, or
processing code exists. Images, galleries, hashes, deduplication, ordering,
resizing, thumbnails, WebP, metadata, watermarking, video URLs, approval, and
orphan cleanup are absent.

Media descriptions under `docs/03_admin_panel.md` are planned behavior only.
No duplicated active media folder was found.

## 14. API and frontend status

All routes use `/api/v1` except root `/` and `/health`. No authentication or
authorization dependency exists; every route is public.

### Current routes

- Health: `GET /api/v1/health/`, `GET /`, `GET /health`.
- Execution: `POST/GET /api/v1/jobs`, `GET /api/v1/jobs/{job_id}`.
- Products: `POST/GET /api/v1/products`,
  `GET/PATCH/DELETE /api/v1/products/{product_id}`.
- Attribute Types: `POST/GET /api/v1/attribute-types`,
  `GET/PATCH/DELETE /api/v1/attribute-types/{id}`.
- Categories: `POST/GET /api/v1/categories`,
  `GET /api/v1/categories/tree`,
  `GET/PATCH/DELETE /api/v1/categories/{id}`.
- Attributes: `POST/GET /api/v1/attributes`,
  `PATCH /api/v1/attributes/{id}`,
  `GET /api/v1/categories/{id}/attributes`,
  `PATCH /api/v1/categories/{id}/attributes/reorder`.
- Warehouses and Inventory: full soft-delete CRUD/list routes.
- Movements: create/list/get/reverse.
- Reservations: create/list/get/fulfill/release/cancel/expire.

Pagination is present on major list endpoints. Filters are uneven: Inventory,
movements, and reservations are richer; Product is limited to `active_only`.
Service-layer mutations own commit/rollback for stabilized Catalog and
Inventory operations. Some GET/list routers call repositories directly, which
is read-only but inconsistent with service-only access.

There is no frontend. Empty root scaffold folders do not contain UI code.

## 15. Database and migration status

### Current modeled tables

- Execution: `jobs`, `job_attempts`, `business_events`.
- Catalog: `categories`, `attribute_definitions`, `category_attributes`,
  `products`.
- Frozen Inventory: `warehouses`, `inventory`, `inventory_movements`,
  `inventory_reservations`.

PostgreSQL-specific JSONB is used for job/event payloads and attribute
validation rules. Status/data-type values are application strings protected
by some check constraints; native PostgreSQL enums are not used.

Catalog and Inventory use soft deletion where applicable. Version columns are
manually incremented but are not configured as SQLAlchemy optimistic-lock
tokens. Timestamps are inconsistent: mixin-backed mutable entities have both
timestamps; immutable movement/event/attempt records use explicit subsets.

Key FK behavior:

- Category parent and Product category: `RESTRICT`.
- CategoryAttribute category: `CASCADE`; attribute: `RESTRICT`.
- Inventory references Product/Warehouse with `RESTRICT`.
- Job attempts cascade with Job.

### Alembic chain

```text
cea65f170298
  → 8b2f4d1c6a10
  → d4a9c8e7f621
  → eb5f2829e72e
  → f1a2b3c4d5e6
  → b2c3d4e5f6a7
  → c3d4e5f6a7b8 (head/current)
```

- One head; current database is at head.
- `alembic check`: no new upgrade operations.
- Models and migrations both represent the same 11 tables.
- `backend/alembic/env.py` imports execution, Catalog, and Inventory models.
- `cea65f170298_initial_database_schema.py` is an empty base revision with
  unused Alembic/SQLAlchemy imports.
- Human-pattern revision IDs for the three Inventory revisions are unusual but
  unique and form a valid chain.
- `eb5f2829e72e` and all Inventory migrations are untracked even though the
  live database depends on them. This is the largest migration/reproducibility
  risk.
- Existing migrations must remain immutable.

## 16. Test and quality status

Pytest collected 29 tests from 9 files:

- Catalog: 12 tests across CRUD, transactions, and unit validation.
- Execution: 2 schema/enum unit tests.
- Health: 2 TestClient tests.
- Inventory: 10 CRUD/movement/reservation/transaction tests.
- Boundary: 3 static/integration/mapper tests.

Integration tests call `http://localhost:8000/api/v1` and therefore require
the running Compose stack and share the development database. They use
GUID-suffixed data and cleanup via soft deletion, so finalized rows accumulate
and tests are not fully isolated. Unit transaction tests use mocks. One
database constraint test may skip when prerequisite references do not exist;
the observed run had no skips.

There is no coverage plugin/configuration and no coverage percentage was
produced. There are no tests for supplier/import/matching/pricing/AI/scraper/
media/publishing because those modules do not exist. Execution lacks worker
integration, retry, stale recovery, and API integration coverage.

Quality configuration:

- Ruff and Black: 88-character line length in `backend/pyproject.toml`.
- Mypy has strict settings but was not requested or run; no CI enforces it.
- Pytest discovers only `backend/tests`.
- No CI configuration was found.
- Full Ruff reports two F401 findings in
  `backend/alembic/versions/cea65f170298_initial_database_schema.py`.
- One Starlette warning reports deprecated `httpx` use and recommends
  `httpx2`.

## 17. Runtime and infrastructure status

`docker-compose.yml` runs:

- FastAPI API on host port 8000, bind-mounted `./backend:/app`, with reload.
- PostgreSQL 15 with persistent `postgres_data`.
- Redis 7 with persistent `redis_data`.
- One execution worker polling PostgreSQL.

All four services were running; API, PostgreSQL, and Redis were healthy.
Worker healthcheck is explicitly disabled.

Redis is configured and running but no application code uses it. The worker
uses PostgreSQL polling, not Redis. There are no n8n, Ollama, Open WebUI,
object-storage, scheduler, or file-storage services/references in executable
configuration.

Configuration risks:

- `.env` is ignored, which is correct for secrets, but secret rotation and
  production secret management are not defined.
- `.env.example` includes development credentials.
- `backend_cors_origins` defaults to `["*"]` while credentials are allowed.
- Settings names (`APP_ENV`, `BACKEND_CORS_ORIGINS`) do not match the example's
  `ENVIRONMENT` and `ALLOWED_ORIGINS`; those example values will not populate
  the declared settings.
- API reload and a source bind mount are development-only choices.
- No authentication, TLS proxy, production Compose overlay, metrics, or
  scheduled task infrastructure exists.

## 18. Dependency-boundary verification

Confirmed:

- Catalog does not import Inventory.
- Inventory imports Catalog `Product`; direction is one-way.
- Product creation/update/deactivation does not create or require Inventory.
- No future module exists, so none is currently forced to use Inventory.
- Supplier Feed, Import, Matching, Pricing, AI, Scraper, Media, Publishing,
  and ERP Sync can be introduced without Inventory if the documented boundary
  is followed.

Minor structural coupling:

- `backend/app/api/router.py` eagerly imports the Inventory router so the
  Inventory package must remain importable for application startup.
- `backend/alembic/env.py` imports Inventory models so Alembic sees its frozen
  tables.

These are registration/metadata dependencies, not business workflow
dependencies. No hidden Inventory call from Catalog was found.

## 19. Functional capability matrix

| Capability | Status | Existing paths | DB | API | Tests | Blocking issue | Recommended next action |
|---|---|---|---:|---:|---:|---|---|
| Categories | COMPLETE | `catalog/models.py`, `service.py`, `router.py` | yes | yes | yes | content fields absent but CRUD complete | freeze CRUD contract |
| Category hierarchy | COMPLETE | `Category.parent_id`, tree service/route | yes | yes | yes | no path materialization | retain adjacency model |
| Products | PARTIAL | Catalog Product stack | yes | yes | yes | product-information fields absent | extend only after source/import model |
| Identifiers | PARTIAL | `code`, `sku`, `ean`, `mpn` | yes | yes | yes | no GTIN validation/source mapping | define normalized identifier policy |
| Brands/manufacturers | PARTIAL | Product string fields | yes | yes | yes | no canonical entities/aliases | design normalization with matching |
| Attribute definitions | COMPLETE | `AttributeDefinition` stack | yes | yes | yes | overlapping façade semantics | document canonical API |
| Category attributes | PARTIAL | `CategoryAttribute` | yes | partial | yes | no direct link/unlink API | add only when UI workflow is defined |
| Product attribute values | ABSENT | none | no | no | no | no value entity | design after import/matching foundation |
| Short descriptions | ABSENT | none | no | no | no | no content model | content/provenance sprint |
| Long descriptions | ABSENT | none | no | no | no | no content model | content/provenance sprint |
| Specifications | ABSENT | none | no | no | no | no product values/content | content and attribute-value sprint |
| Multilingual content | ABSENT | none | no | no | no | no locale/version model | content/provenance sprint |
| Supplier definitions | ABSENT | docs only | no | no | no | no source identity | next sprint foundation |
| Supplier items | ABSENT | none | no | no | no | no stable supplier item | next sprint foundation |
| Supplier offers | ABSENT | none | no | no | no | no price/availability snapshots | next sprint foundation |
| Price-list upload | ABSENT | none | no | no | no | no storage/upload contract | next sprint foundation |
| XML import | ABSENT | docs only | no | no | no | no parser | later import adapter |
| CSV import | ABSENT | docs only | no | no | no | no parser | first concrete adapter |
| Excel import | ABSENT | docs only | no | no | no | no dependency/parser | second concrete adapter |
| API import | ABSENT | docs only | no | no | no | no connector abstraction | later connector |
| Field mapping | ABSENT | none | no | no | no | no mapping schema | next sprint foundation |
| Normalization | ABSENT | none | no | no | no | no typed normalized row | next sprint foundation |
| Import history | ABSENT | generic Jobs only | no | no | no | Job is insufficient | import batch/source entities |
| Import errors | ABSENT | generic job error only | no | no | no | no row-level errors | import error entity |
| Product matching | ABSENT | none | no | no | no | no supplier item mapping | stage after normalized feeds |
| AI-assisted matching | ABSENT | docs only | no | no | no | no matching or AI layer | later matching enhancement |
| Manual match review | ABSENT | docs only | no | no | no | no candidate/decision model or UI | matching review sprint |
| New-product creation | PARTIAL | Catalog POST Product | yes | yes | yes | not connected to unmatched items/review | connect after matching |
| Pricing rules | ABSENT | docs only | no | no | no | no supplier offers/rules | after matching/content foundation |
| Retail price calculation | ABSENT | docs only | no | no | no | no monetary model | pricing sprint |
| Price history | ABSENT | docs only | no | no | no | no effective-dated price | pricing sprint |
| AI descriptions | ABSENT | `ai_prompt` field only | no | no | no | no content/AI provider | AI enrichment sprint |
| AI specifications | ABSENT | docs only | no | no | no | no output storage/approval | AI enrichment sprint |
| AI attributes | ABSENT | prompt fields only | no | no | no | no product values | AI enrichment sprint |
| AI translation | ABSENT | docs only | no | no | no | no multilingual content | AI enrichment sprint |
| AI categorization | ABSENT | docs only | no | no | no | no provider/review | AI enrichment sprint |
| SEO generation | ABSENT | docs only | no | no | no | no SEO content fields | content/AI sprint |
| Manufacturer scraping | ABSENT | docs only | no | no | no | no scraper | scraper sprint |
| Generic scraping | ABSENT | docs only | no | no | no | no fetch/extraction layer | scraper sprint |
| Image ingestion | ABSENT | docs only | no | no | no | no media/source model | media sprint |
| Image processing | ABSENT | docs only | no | no | no | no storage/tooling | media sprint |
| Video ingestion | ABSENT | docs only | no | no | no | no media model | media sprint |
| Human approval | ABSENT | docs only | no | no | no | no proposal/version workflow | cross-cutting approval foundation |
| ERP synchronization | ABSENT | docs only | no | no | no | no adapter/outbox contract | later integration |
| Web-shop publishing | ABSENT | docs only | no | no | no | no publication model | later integration |
| Audit history | PARTIAL | Job attempts/events, version counters | partial | jobs only | partial | no Catalog change history | add domain audit/provenance |
| Job monitoring | PARTIAL | Execution module | yes | yes | unit only | handlers are demo-only; no auth | integrate with future import jobs |

## 20. Critical issues

1. **Untracked canonical migrations and active Inventory source.** A clone of
   the branch cannot reproduce the live database or API.
2. **Large mixed working tree.** Catalog, migration recovery, Inventory,
   execution, tests, and documentation are not separated into reviewable
   commits.
3. **Core workflow is absent.** Supplier/source identity and raw/normalized
   feed persistence do not exist, so Matching, Pricing, AI, and Publishing
   cannot be built on reliable inputs.
4. **Product information model is too small for the stated goal.** No content,
   product attribute values, multilingual/provenance/approval/media data.
5. **Overlapping Catalog schema/API concepts.** `schemas.py` versus `schemas/`
   and Attribute Types versus Attributes increase maintenance ambiguity.
6. **Tests use the shared development database.** Soft-deleted disposable rows
   accumulate and concurrency/order isolation is limited.
7. **No authentication and permissive CORS.** Current API is development-only.
8. **Execution is generic but unintegrated.** Worker handles only demo jobs;
   Redis is unused and no worker healthcheck/CI exists.
9. **Repository hygiene.** Malformed artifact, empty duplicated scaffolds,
   stale bytecode architecture remnants, and two virtual environments obscure
   the active tree.

## 21. Recommended development order

### Must fix before development

1. Review and commit the currently active migration chain, Inventory package,
   Catalog stabilization, boundary tests, and documentation in coherent units.
2. Manually review and remove only confirmed malformed/stale artifacts.
3. Decide the canonical `schemas/` package and document the Attribute Type
   façade to prevent another architecture split.
4. Establish an isolated test database strategy and a minimal CI pipeline.
5. Correct configuration-name drift and define development security posture.

### Foundation required next

1. Supplier Source and Feed domain.
2. Immutable source-file/import-batch/raw-row persistence.
3. Supplier-specific mapping definitions and typed normalized rows.
4. Supplier Item and effective Supplier Offer identity, with availability
   explicitly separate from Inventory.
5. Row validation, checksums/idempotency, errors, and statistics.
6. One initial adapter (CSV) proving the complete ingestion contract.

### Second-stage modules

1. Deterministic Product Matching and persistent match decisions.
2. Manual review and controlled Catalog create/update proposals.
3. Product attribute values and multilingual, versioned, source-aware content.
4. AI Enrichment operating on proposals with structured validation and human
   approval.
5. Pricing rules and effective-dated prices based on Supplier Offers.
6. Media ingestion/processing and scraper source capture.

### Later integrations

1. Approval workflow across product/content/price/media proposals.
2. Web-shop publishing.
3. External ERP synchronization with idempotent adapters and audit/outbox.
4. Operational authentication, authorization, observability, and production
   deployment controls.

### Frozen optional modules

- Inventory
- Inventory Movements
- Inventory Reservations

Do not extend or couple these modules to Supplier Feed, Import, Matching,
Pricing, AI, Media, or Publishing.

## 22. Exact proposed next sprint

**Sprint: Supplier Source and Import Contract Foundation**

The sprint should define and implement only the source-of-truth boundary needed
before parsing and matching:

1. Supplier identity and active configuration.
2. Source receipt metadata: supplier, source type, original filename/location,
   checksum, received time, and immutable raw-file reference.
3. Import batch lifecycle with idempotency key, status, counts, timestamps, and
   error summary.
4. Supplier field-mapping version and a normalized-row contract.
5. Persistent Supplier Item identity and Supplier Offer snapshots containing
   supplier SKU, identifiers, description, purchase-price inputs, tax inputs,
   and supplier availability.
6. Row-level validation/error persistence.
7. A single CSV vertical slice: receive, checksum, parse, map, normalize,
   persist, retry idempotently, and report statistics.
8. Collected unit/integration/rollback tests and explicit guards proving no
   Inventory balance, movement, or reservation is touched.

Explicitly exclude Product Matching, Catalog auto-creation, Pricing formulas,
AI, scraping, media, ERP/web-shop synchronization, procurement, sales,
invoicing, and accounting from this sprint.
