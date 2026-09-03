# Repository cleanup and stabilization report

Date: 2026-07-23
Branch: `feature/product-core`
Scope: cleanup and verification only

## 1. Executive summary

The repository was inspected for Git state, generated artifacts, duplicate
architectures, imports, TODO markers, migrations, ORM metadata, routes, tests,
documentation, infrastructure, and Inventory coupling.

Only unquestionably generated content and empty directories were removed. No
tracked file, business source, migration, API, database object, or runtime
configuration was changed. The malformed root artifact and ambiguous duplicate
source concepts were intentionally retained.

The application is operational: syntax, mapper configuration, Alembic, and all
29 tests pass. The repository is not yet a stable development baseline because
canonical active migrations, the Inventory module, stabilization tests, and
architecture documentation remain untracked; Ruff also has two findings in
the original empty migration.

## 2. Git status

- Branch: `feature/product-core`.
- Tracking: one commit ahead of `origin/feature/product-core`.
- Staged files: none.
- Tracked deletions or renames: none.
- Merge conflicts or conflict markers: none.
- Modified tracked files: 13.
- Existing tracked diff: 709 insertions and 124 deletions.

Modified tracked files:

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

Important untracked files that are active and must be retained:

- `backend/alembic/versions/eb5f2829e72e_add_products_table.py`
- `backend/alembic/versions/f1a2b3c4d5e6_inventory_foundation.py`
- `backend/alembic/versions/b2c3d4e5f6a7_inventory_movements.py`
- `backend/alembic/versions/c3d4e5f6a7b8_inventory_reservations.py`
- `backend/app/modules/inventory/`
- the collected Catalog, Inventory, transaction, reservation, and boundary
  tests under `backend/tests/`
- `docs/architecture/module-boundaries.md`
- the audit documents under `docs/audits/`

No generated files were found accidentally tracked by Git. Generated
bytecode, cache, and egg-info artifacts were ignored.

## 3. Files cleaned

Removed generated content:

- all repository-source `__pycache__` directories outside `.venv`, `.venv-1`,
  `.git`, and `.agents`;
- all corresponding `.pyc` files, including stale Python 3.12 and 3.13
  bytecode;
- root and backend `.pytest_cache` directories;
- root and backend `.ruff_cache` directories;
- `backend/ai_cenovnici_api.egg-info`;
- the ignored `backend_product_core_v1/` snapshot after confirming it
  contained only pytest cache, bytecode, and egg-info rather than source.

Removed empty directories:

- obsolete bytecode-only Catalog package remnants:
  `catalog/models/`, `catalog/repository/`, `catalog/services/`, and
  `catalog/tests/`;
- empty root scaffolds: `app/`, `tests/`, `config/`, `dagster/`, `data/`, and
  `docker/`;
- empty duplicated scaffold `AI-Cenovnici/`;
- empty parents left by the generated snapshot cleanup.

Virtual environments were intentionally excluded. No tracked deletion appears
in Git status because every removed item was ignored, generated, or empty.

## 4. Duplicate items

### Active ambiguity

`backend/app/modules/catalog/schemas.py` and
`backend/app/modules/catalog/schemas/` both represent Catalog schemas. Python
currently resolves `app.modules.catalog.schemas` to the package, whose
`__init__.py` exports the active split schemas. The monolithic tracked
`schemas.py` is legacy/shadowed but was not removed because it remains tracked
and cleanup authorization did not establish that its history can be discarded.

### Intentional repeated filenames

`models.py`, `repository.py`, `service.py`, `router.py`, `schemas.py`, and
`enums.py` repeat across Catalog, Execution, and Inventory. They belong to
different modules and are not duplicates.

### Documentation layout

High-level tracked documents remain at repository root while numbered design
documents and audits live under `docs/`. They overlap conceptually but are not
byte-for-byte duplicates. No documentation was removed.

## 5. Remaining suspicious items

### Malformed root artifact

`s -ExecutionPolicy RemoteSigned) ; (& cAI-Monitor-Hub.venvScriptsActivate.ps1)`
is an untracked 3,347-byte root file. Nothing imports or references it. It
appears to be an accidental PowerShell command capture, but it was retained
because it is not provably generated and the cleanup rules prohibit deleting
uncertain data.

### Duplicate virtual environments

Both `.venv/` and `.venv-1/` exist and are ignored. The configured
`<repository-root>\.venv` interpreter currently reports a broken base-Python
path, while Docker validation works. Neither environment was removed because
they may contain user-installed dependencies.

### Working-tree risk

Four applied migrations and the complete active Inventory module are
untracked. Their removal would break reproducibility and application imports.
They must be reviewed and included in a checkpoint rather than cleaned.

## 6. Import audit

Confirmed:

- no Catalog or Execution module imports Inventory;
- Inventory imports Catalog `Product`, preserving the allowed downstream
  dependency;
- no import cycle prevents SQLAlchemy mapper configuration;
- all application imports compile and all registered routers load;
- no old split-service or old router source path remains imported;
- Ruff reports no unused import in current application/test source.

Issues:

- `app.modules.catalog.schemas` is shadowed by both a module and package with
  the same qualified name. The package is active.
- `backend/alembic/versions/cea65f170298_initial_database_schema.py` imports
  `alembic.op` and `sqlalchemy` without using them.
- `backend/app/api/router.py` eagerly imports Inventory for backward-compatible
  route registration. This is application registration, not business coupling.
- `backend/alembic/env.py` imports all model modules so metadata includes all
  tables; this is required for drift detection.

No speculative import change was made.

## 7. Migration audit

Chain:

```text
cea65f170298
  → 8b2f4d1c6a10
  → d4a9c8e7f621
  → eb5f2829e72e
  → f1a2b3c4d5e6
  → b2c3d4e5f6a7
  → c3d4e5f6a7b8
```

- One head: `c3d4e5f6a7b8`.
- Current database: `c3d4e5f6a7b8`.
- No orphan or duplicate revision.
- No schema drift.
- Metadata loads Catalog, Execution, and Inventory.
- Eleven mapped tables match the migration chain.
- `cea65f170298` is an empty base revision with two unused imports.
- The sequential-looking Inventory revision IDs are nonstandard but valid and
  unique.
- The recovered Product migration and all Inventory migrations remain
  untracked, which blocks repository readiness.

No migration was edited or applied.

## 8. SQLAlchemy audit

Active models:

- Catalog: `Category`, `AttributeDefinition`, `CategoryAttribute`, `Product`.
- Execution: `Job`, `JobAttempt`, `BusinessEvent`.
- Frozen Inventory: `Warehouse`, `Inventory`, `InventoryMovement`,
  `InventoryReservation`.

No orphan or duplicate active ORM model was found. Relationship mapping
configures successfully.

Suspicious or inconsistent patterns:

- Attribute Types are an API façade over `AttributeDefinition`, not a separate
  model. This is intentional but semantically overlapping.
- Version fields are manually incremented and are not SQLAlchemy optimistic
  concurrency tokens.
- Soft deletion is implemented for Catalog and mutable Inventory entities, but
  immutable ledger/event records use lifecycle status instead.
- Product/warehouse foreign keys in Inventory use `RESTRICT`, correctly making
  hard deletion unsafe; public deletion is soft.
- JSONB is used for attribute validation and execution payloads.
- ORM statuses are strings; only some are protected with database checks.

## 9. API audit

Registered route groups:

- health/root;
- Execution jobs;
- Catalog products, categories, attributes, and Attribute Types;
- frozen Warehouses, Inventory, Movements, and Reservations.

No duplicate method/path pair or broken prefix was detected through OpenAPI
generation and test execution.

Issues:

- no authentication or authorization exists;
- Product filtering is minimal compared with other list APIs;
- Attributes have create/list/update but no GET-by-ID or deactivate endpoint;
- Attribute Types and Attributes expose overlapping `AttributeDefinition`
  rows;
- some read routes use repositories directly while mutations use services;
- schema module/package shadowing remains;
- no orphan schema currently breaks imports, but the tracked monolithic
  Catalog schemas module appears inactive.

No route or schema was modified.

## 10. Test audit

Pytest collects 29 tests from:

- `test_catalog_crud.py`
- `test_catalog_transactions.py`
- `test_catalog_unit.py`
- `test_execution_unit.py`
- `test_health.py`
- `test_inventory_crud.py`
- `test_inventory_movements.py`
- `test_inventory_reservations.py`
- `test_inventory_transactions.py`
- `test_module_boundaries.py`

There are no executable smoke scripts outside `backend/tests` after cleanup;
only stale compiled evidence of an old `test_products_endpoint.py` existed and
was removed as bytecode.

Risks:

- API integration tests target the running development service and shared
  PostgreSQL database;
- GUID suffixes prevent value collisions, but soft-deleted rows accumulate;
- several large CRUD scenarios are grouped into one test function;
- fixtures defining the same API client are duplicated across integration
  files;
- one movement constraint test can skip if database references are absent;
- no coverage plugin/configuration or CI workflow exists;
- Execution worker behavior has limited unit coverage and no integration test.

No order dependency failed in the observed full run.

## 11. Documentation audit

- Root `README.md` is empty and does not onboard developers.
- `backend/README.md` documents backend setup but does not cover the full
  stabilized working tree.
- Root design documents and numbered `docs/` files describe a much broader
  future system than current code.
- `docs/architecture/module-boundaries.md` is the current Inventory isolation
  rule.
- `docs/audits/full-project-audit.md` is a pre-cleanup snapshot; paths reported
  there as cleanup candidates may now be removed.
- No central documentation index or explicit “implemented versus planned”
  legend exists.
- No broken executable document reference affects runtime, but plans should not
  be mistaken for implemented modules.

## 12. Infrastructure audit

Docker Compose runs API, PostgreSQL 15, Redis 7, and one database-polled
Execution worker.

Findings:

- API uses a development bind mount and `uvicorn --reload`.
- Redis is configured and healthy but unused by application code.
- Worker healthcheck is disabled.
- No n8n, Ollama, Open WebUI, scheduler, object storage, or frontend service is
  configured.
- `.env` is correctly ignored.
- `.env.example` contains development defaults.
- Settings declare `APP_ENV` and `BACKEND_CORS_ORIGINS`, while `.env.example`
  documents `ENVIRONMENT` and `ALLOWED_ORIGINS`; those names do not align.
- CORS defaults to wildcard origins while credentials are enabled.
- No authentication, CI, production Compose overlay, or secret-management
  integration exists.
- Root and backend health endpoints both exist with different paths.

No infrastructure file was changed.

## 13. Inventory isolation verification

- Inventory remains unchanged and frozen.
- Catalog has no Inventory import.
- Execution has no Inventory import.
- No Supplier, Import, Matching, Pricing, AI, Scraper, Media, or Publishing
  module exists or depends on Inventory.
- Inventory depends one-way on Catalog Product.
- Inventory routes remain registered for backward compatibility.
- Boundary guards in `backend/tests/test_module_boundaries.py` pass.

## 14. TODO audit

No `TODO`, `FIXME`, `XXX`, `HACK`, `TEMP`, `DEPRECATED`, or `LEGACY` marker was
found in repository source/documentation after excluding Git internals,
virtual environments, caches, and the removed generated snapshot.

This does not mean technical debt is absent; the concrete debt is listed below.

## 15. Validation results

- `git diff --check`: one existing trailing blank-line warning in
  `backend/app/modules/catalog/repository.py`; no fix was made because that file
  contains prior user work.
- Ruff: failed with two F401 findings in the empty initial migration only.
- Read-only Python compilation: passed for 66 Python files.
- SQLAlchemy mapper configuration: passed for 11 tables.
- Alembic heads: one, `c3d4e5f6a7b8`.
- Alembic current: `c3d4e5f6a7b8`.
- Alembic check: no new upgrade operations.
- Pytest collection: 29 tests.
- Full pytest: 29 passed.
- Warning: one existing Starlette `TestClient`/`httpx2` deprecation warning.

Validation used `PYTHONDONTWRITEBYTECODE=1`, Ruff `--no-cache`, and pytest
without the cache provider so cleanup artifacts were not recreated.

## 16. Remaining technical debt

Priority blockers:

1. Review and checkpoint the active untracked migrations, Inventory source,
   collected tests, and architecture documentation.
2. Resolve the malformed root artifact manually.
3. Choose and document the canonical Catalog schema layout; then separately
   retire the shadowed monolithic module if approved.
4. Decide whether to clean the two initial-migration imports without rewriting
   migration history.
5. Repair or retire the duplicate `.venv-1`; verify the broken local `.venv`
   interpreter reference.
6. Add isolated test-database lifecycle and CI.

Non-blocking debt:

- empty root README;
- settings/example environment variable drift;
- unused Redis;
- disabled worker healthcheck;
- permissive unauthenticated development API;
- duplicate integration fixtures;
- missing coverage measurement;
- Starlette TestClient deprecation;
- mixed line endings and one `git diff --check` warning.

## 17. Repository readiness

**Not ready as a stable development baseline.**

Runtime behavior is stable, but source-control reproducibility is not. A fresh
checkout would lack the migration revisions and Inventory implementation
required by the current router, metadata, database, and tests. The working tree
also mixes multiple stabilization efforts and contains a malformed untracked
artifact.

Required checkpoint preparation:

- include all active migrations and active source/tests/docs;
- review the 13 modified tracked files as coherent changes;
- retain Inventory unchanged;
- manually resolve the malformed root file;
- record or resolve the remaining Ruff/diff-check warnings.

## 18. Commit checkpoint summary

Files modified by Sprint 0:

- `docs/audits/repository-cleanup-report.md` only.

Files removed:

- ignored Python bytecode and `__pycache__`;
- pytest/Ruff caches;
- generated egg-info;
- generated/cache-only `backend_product_core_v1/`;
- empty obsolete Catalog package remnants;
- empty root and duplicated scaffold directories.

Files intentionally kept:

- all tracked business source and migrations;
- all active untracked migrations, Inventory source, tests, and documentation;
- malformed root artifact pending human review;
- both virtual environments;
- tracked legacy `backend/app/modules/catalog/schemas.py`.

Remaining warnings:

- two Ruff F401 findings in `cea65f170298_initial_database_schema.py`;
- one trailing blank-line `git diff --check` warning;
- one Starlette/httpx deprecation warning;
- LF/CRLF conversion notices on modified tracked files.

Recommended commit message:

```text
chore: repository cleanup and baseline stabilization
```

Do not create the checkpoint until all active untracked files and the malformed
artifact have been explicitly reviewed.
