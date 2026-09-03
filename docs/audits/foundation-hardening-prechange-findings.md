# Foundation Hardening Pre-change Findings

Captured on 2026-07-24 from branch `feature/product-core` before the broad
Foundation Hardening implementation. The working tree already contained the
uncommitted Catalog, Inventory, Product Attribute, Product Content, and
Execution audit work listed by `git status`; this sprint must preserve it.

## Baseline

- Repository inventory: 153 files, including 121 Python files and about 21,700
  Python lines.
- OpenAPI: 152 paths, 223 operations, 134 schemas, zero duplicate operation
  IDs.
- PostgreSQL/Alembic: one head and current revision `d1e2f3a4b5c6`; drift
  check clean; empty database and safe one-revision downgrade/re-upgrade passed.
- Tests: two consecutive runs passed 93/93 with no skips.
- Ruff: standard rules passed.
- Ruff C901: failed for `AttributeValueValidator.normalize` (39) and
  `InventoryService.fulfill_reservation` (13).
- MyPy: 105 errors in 20 files.
- Docker: API healthy; worker running; PostgreSQL healthy; Redis healthy.
- Malformed API matrix: 328 generated requests, zero HTTP 500 responses.

## Findings

| ID | Severity | Module | Location | Confirmed finding |
|---|---|---|---|---|
| FH-001 | Critical | API-wide | `app/api/router.py`; every router | Mutating and administrative endpoints have no authenticated principal or authorization policy. |
| FH-002 | Critical | Catalog | `routers/product_attributes.py:63` | Public `POST /catalog/attribute-seed` mutates canonical configuration without authentication. |
| FH-003 | High | Catalog | `routers/product_attributes.py:79`; `routers/attribute_platform.py:344,408,492` | Routers construct and execute SQL and calculate persistence-backed dashboards. |
| FH-004 | High | Attributes | `attribute_service.py:714`; `platform_service.py:15,54` | Bidirectional service dependency is hidden behind a local import during value recalculation. |
| FH-005 | High | Execution | `worker.py`; `repository.py:61-118` | Worker claims have no lease token, heartbeat, or fencing; stale workers can later finalize an attempt they no longer own. |
| FH-006 | High | Platform | repositories listed below | Required concurrency and failure-injection matrices are incomplete, so lost-update and conflict behavior is not fully proven. |
| FH-007 | High | API/security | `main.py:31-41`; schemas with unbounded text/JSON | No transport request-size ceiling and many domain fields have no maximum length. |
| FH-008 | Medium | Core/security | `core/config.py:13-39`; `main.py:34-39` | Production startup does not reject wildcard credentialed CORS, weak/default secrets, development authentication, or insecure deployment settings. |
| FH-009 | Medium | All repositories | list queries in Execution, Catalog, Inventory | Several offset-paginated queries lack a unique deterministic secondary ordering. |
| FH-010 | Medium | Catalog/Inventory | oversized service files | God classes contain 22-38 public methods and multiple transaction domains. |
| FH-011 | Medium | Static quality | 20 application files | MyPy baseline has 105 errors, including unsafe optional handling and DTO/ORM mismatches. |
| FH-012 | Medium | Dependencies | `pyproject.toml`; `Dockerfile` | Runtime dependency resolution is broad and not reproducible; builds install editable dev dependencies and upgrade pip. |
| FH-013 | Medium | API | generated OpenAPI | Seven operations lack a documented 4xx/default response; errors are not represented by a stable shared schema. |
| FH-014 | Medium | Performance | Catalog dashboard and offset lists | Query amplification, offset degradation, and representative 1,000-product query plans are not measured. |
| FH-015 | Medium | Auditability | event/history models and routers | No authenticated actor or request/correlation identity is propagated consistently into existing audit fields. |
| FH-016 | Low | Compatibility | Product Content `service.py` and `repository.py` | Thin compatibility facades are not used by active imports but may be external public surfaces and must be retained/documented. |

## Reproduction, impact, and correction plan

### FH-001/FH-002

Reproduction: call `POST /api/v1/catalog/attribute-seed` without credentials;
the endpoint returns 200. No router declares a security dependency other than
the database session.

Root cause: authentication and authorization were deferred while business APIs
were registered globally.

Impact: any caller with network access can mutate Catalog, Attributes, Product
Content, Inventory, and Execution. Supplier ingestion would amplify this
untrusted write surface.

Correction: centralized verified bearer authentication, immutable principal,
permission matrix, declarative dependencies, route classification, OpenAPI
security scheme, actor propagation, and 401/403 integration tests.

Compatibility risk: all non-public endpoints will intentionally require
credentials. Migration: none. Test plan: every route class, raw-preview double
gate, seed protection, role matrix, invalid/expired credentials.

### FH-003

Reproduction: static AST/grep finds `select()` and `session.execute()` in the
known Catalog routers.

Root cause: dashboard and platform read features were added directly at the
transport layer.

Impact: SQL ownership, performance policy, and authorization orchestration are
fragmented.

Correction: narrow repository queries and service DTO/orchestration methods;
router boundary tests. Compatibility risk: low if response models and operation
IDs remain unchanged. Migration: none.

### FH-004

Reproduction: `AttributePlatformService` constructs
`ProductAttributeService`, while `ProductAttributeService.write_value`
locally imports and constructs `AttributePlatformService`.

Root cause: formula recalculation was attached after the base write service
without an orchestration boundary.

Impact: implicit temporal coupling and unclear nested transaction ownership.

Correction: an explicit mutation/recalculation coordinator or injected
recalculation port. Compatibility risk: medium because attribute writes, bulk
atomicity, events, and derived values must remain identical. Migration: none.

### FH-005

Reproduction: worker commits a claim, runs a handler without heartbeat, then
reloads by job ID and finalizes without verifying attempt ownership.

Root cause: `locked_by`/`locked_at` are informational rather than a fenced
lease.

Impact: stale recovery can retry a job while the original worker is alive; the
stale worker may later overwrite state or duplicate external effects.

Correction: attempt/lease token, heartbeat, compare-and-set finalization, lease
loss domain error, deterministic stale recovery. Compatibility risk: additive
API/worker behavior; a corrective migration is likely required.

### FH-006 through FH-015

These are reproduced by the baseline matrices and static metrics above. The
implementation plan is respectively: complete independent-session and
failure-injection tests; add configurable transport/domain limits; validate
production profiles; append unique ordering keys; decompose real transaction
domains behind compatibility facades; establish a reviewed MyPy baseline and
remove high-risk errors; lock dependencies; centralize error responses; create
representative query-plan budgets; and propagate stable actor/correlation
identity.

All are relevant to Chapter 3. FH-006, FH-007, FH-008, FH-009, FH-011,
FH-012, FH-013, and FH-015 require no schema migration. FH-005 may require a
new corrective migration. Performance may justify indexes only after
`EXPLAIN ANALYZE` confirms a real gap.

## False positives and retained history

- No top-level import cycle exists; FH-004 is a runtime domain cycle rather
  than an import-time failure.
- Repositories currently contain no commits or FastAPI `HTTPException`.
- Product Content uses the canonical Catalog Product model.
- Product Content sanitization uses Bleach; raw preview is disabled by
  configuration, but still lacks the required permission gate.
- The initial no-op migration and every later Alembic revision are immutable
  migration history, not dead files.
- Empty `__init__.py` files are package markers.
- Product Content facade modules are retained until an external compatibility
  inventory proves they are removable.
