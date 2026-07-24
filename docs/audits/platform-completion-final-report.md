# Platform completion final report

> Historical Foundation evidence snapshot. The post-freeze repository,
> dependency, multi-instance, and release conclusions are superseded by
> [post-freeze-repository-release-final-report.md](post-freeze-repository-release-final-report.md).

Report date: 2026-07-24
Branch: `feature/product-core`
Repository: `<repository-root>`
Application environment: Docker Compose, Python 3.12.13

This report uses exactly two evidence states:

- **CURRENT VERIFIED** — executed against the final application/test source and
  final clean-built images.
- **NOT VERIFIED** — no valid result is available and no result is inferred.

Documentation-only corrections made after the clean build do not change the
application image, migrations, tests, or measured behavior.

## 1. Executive decision

## GO FOR CHAPTER 3 — FOUNDATION FROZEN

**CURRENT VERIFIED:** the final source builds and runs; the Alembic graph is
linear and runtime-tested; all 254 tests pass repeatedly in serial, randomized,
branch-coverage, and xdist modes; critical concurrency and failure invariants
pass on PostgreSQL; restart/recovery exercises pass; the execution claim index,
cursor pagination, 10,023-definition resolved-attribute workload, and worker
scaling are measured.

**CURRENT VERIFIED:** no unresolved issue was found that can cause unauthorized
mutation, database drift, lost updates, overselling, invalid inventory, stale
job finalization, duplicate finalization, broken deployment, or an unbounded
ordinary resolved-attribute response.

**NOT VERIFIED:** the locked dependency set has not completed an external
vulnerability-advisory scan. This is an operational release check, not a
correctness failure; `pip check` and exact lock integrity pass.

## 2. Completion classification

| Class | State | Final content |
|---|---|---|
| A. Implemented and proven | **CURRENT VERIFIED** | Application source, migrations, Docker images, static gates, 254-test suite, critical coverage, concurrency, failure injection, recovery, API contract, and benchmarks |
| B. Implemented but not proven | **CURRENT VERIFIED** | None within the Foundation scope |
| C. Not implemented | **CURRENT VERIFIED** | None required by this closure |
| D. External/operational dependency | **NOT VERIFIED** | External dependency vulnerability advisory scan; usable host Python installation/local `.venv` |
| E. Accepted non-blocking debt | **CURRENT VERIFIED** | Lower non-critical global branch coverage, retained offset compatibility, process-local rate-limit/metrics caveat, optional external OIDC, and the intentionally uncommitted working tree |

## 3. Final Git and file inventory

**CURRENT VERIFIED:** expanded porcelain status contains 236 entries:

- 96 Git-tracked files in the repository;
- 47 tracked modified files;
- 189 untracked files;
- 0 staged, deleted, renamed, or conflicted files;
- 285 Git-visible files after combining tracked and untracked paths;
- 213 Python files and 33,746 physical Python lines;
- 143 application files;
- 45 test files;
- 20 Alembic revisions;
- 5 benchmark/report scripts.

The 189 untracked files are exactly:

| Group | Files |
|---|---:|
| Alembic revisions | 13 |
| Core application additions | 10 |
| Catalog additions | 39 |
| Inventory additions | 7 |
| Execution additions | 1 |
| Product Content additions | 40 |
| Collected tests | 34 |
| Scripts and benchmark seed | 5 |
| Architecture documents | 15 |
| Audit artifacts/reports | 12 |
| Operations documents | 6 |
| Security documents | 5 |
| Lock/baseline configuration | 2 |
| **Total** | **189** |

The 47 tracked modified files are:

```text
.env.example
backend/Dockerfile
backend/alembic/env.py
backend/app/api/router.py
backend/app/api/routes/health.py
backend/app/core/config.py
backend/app/core/logging.py
backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/mixins.py
backend/app/main.py
backend/app/modules/catalog/enums.py
backend/app/modules/catalog/models.py
backend/app/modules/catalog/repository.py
backend/app/modules/catalog/router.py
backend/app/modules/catalog/routers/attribute_types.py
backend/app/modules/catalog/routers/products.py
backend/app/modules/catalog/schemas/__init__.py
backend/app/modules/catalog/schemas/attribute_types.py
backend/app/modules/catalog/schemas/attributes.py
backend/app/modules/catalog/schemas/categories.py
backend/app/modules/catalog/schemas/products.py
backend/app/modules/catalog/service.py
backend/app/modules/execution/handlers.py
backend/app/modules/execution/models.py
backend/app/modules/execution/repository.py
backend/app/modules/execution/router.py
backend/app/modules/execution/schemas.py
backend/app/modules/execution/service.py
backend/app/modules/execution/worker.py
backend/app/modules/inventory/models.py
backend/app/modules/inventory/repository.py
backend/app/modules/inventory/router.py
backend/app/modules/inventory/schemas.py
backend/app/modules/inventory/service.py
backend/pyproject.toml
backend/tests/test_catalog_crud.py
backend/tests/test_catalog_transactions.py
backend/tests/test_catalog_unit.py
backend/tests/test_execution_unit.py
backend/tests/test_health.py
backend/tests/test_inventory_crud.py
backend/tests/test_inventory_movements.py
backend/tests/test_inventory_reservations.py
backend/tests/test_inventory_transactions.py
backend/tests/test_module_boundaries.py
docker-compose.yml
```

**CURRENT VERIFIED:** the required pre-change checkpoint is preserved in
[`final-validation-working-tree-inventory.md`](final-validation-working-tree-inventory.md).
No reset, restore, commit, or push was performed.

**CURRENT VERIFIED:** 20 generated cache directories and one local `.coverage`
file were removed after verifying every target was strictly below
`<repository-root>\backend`. No temporary source/test artifact remains.

## 4. Canonical ownership and compatibility façades

**CURRENT VERIFIED:** module-boundary, import, AST, and mapper tests establish
this ownership:

```text
router
  -> command/query service
  -> flush-only repository
  -> SQLAlchemy model
  -> PostgreSQL
```

| Domain | Canonical ownership | Intentional compatibility surface |
|---|---|---|
| Catalog | `catalog/models.py`, responsibility repositories/services, `schemas/`, routers | `catalog/repository.py`, `catalog/service.py`, and explicit `legacy_attribute_*` delegates |
| Inventory | `inventory/models.py`, balance/movement/reservation repositories and services | monolithic public repository/service imports retained for API compatibility |
| Product Content | `product_content/models.py`, responsibility repositories/services, routers | `repository.py`/`service.py` façades and plural export modules |
| Execution | `execution/models.py`, repository, service, worker, handlers | no duplicate ownership |

**CURRENT VERIFIED:** Catalog owns the only canonical `Product` model. Attribute
Types remain an API façade over `AttributeDefinition`; there is no
`AttributeType` table/model. No accidental module/package same-name collision,
duplicate Product ownership, hidden Inventory import into Catalog, router SQL,
router transaction ownership, or repository commit exists.

**CURRENT VERIFIED:** the compatibility façades share the caller's session and
do not duplicate domain persistence. No valid duplicate or obsolete
implementation is safe to remove in this closure.

## 5. Python environment and locked dependencies

### Authoritative Docker environment

**CURRENT VERIFIED:**

| Component | Version |
|---|---|
| Python | 3.12.13 |
| pip | 26.1.2 |
| FastAPI | 0.139.2 |
| SQLAlchemy | 2.0.51 |
| Alembic | 1.18.5 |
| Pydantic | 2.13.4 |
| asyncpg | 0.31.0 |
| pytest | 8.4.2 |
| coverage | 7.15.2 |
| pytest-xdist | 3.8.0 |
| pytest-randomly | 4.1.0 |
| MyPy | 1.20.2 |
| Ruff | 0.12.5 |

**CURRENT VERIFIED:** `backend/requirements.lock` contains 74 lines/1,384
bytes and has SHA-256
`478D1C33931E44CB61053C9BA9B7B7B99A650706C8BA8574FD305B07825490DE`.
`pip check` reports `No broken requirements found`.

### Host environment

**NOT VERIFIED:** `.venv\pyvenv.cfg` targets removed Python 3.12.10 at
`%LOCALAPPDATA%\Programs\Python\Python312\python.exe`;
`.venv\Scripts\python.exe --version` reports that no Python exists there, and
the Windows `py` launcher is absent. No compatible host interpreter was
available from which to recreate it without adding an external installation.
All mandatory validation therefore used the clean Docker Python 3.12.13 image,
as permitted by the closure procedure.

## 6. Final clean build and running platform

**CURRENT VERIFIED:** both final images were built from the current working tree
with:

```text
docker compose build --no-cache api worker
```

| Image | Image ID | Created |
|---|---|---|
| API | `sha256:c47d0e84efc41961fc98d0ea11856d04fa1ac9269c8d978053f1678517a37590` | `2026-07-24T11:55:19.844979643Z` |
| Worker | `sha256:fffd90b8d5c2db7c62f4d2f472cedcf76b80b3924a7d1cfb69af865f4412ec79` | `2026-07-24T11:55:19.844979643Z` |

**CURRENT VERIFIED:** a baked-source/host comparison covered 218 selected
application, migration, test, script, and configuration files: 0 missing,
0 extra, and 0 hash mismatches.

**CURRENT VERIFIED:** the complete Compose stack was stopped and started after
the clean build. Final state:

| Service | Final state |
|---|---|
| API | healthy, port 8000 |
| PostgreSQL 15 | healthy, accepting connections |
| Redis 7 | healthy, `PONG` |
| Worker 1 | running |
| Worker 2 | running |

**CURRENT VERIFIED:** root `200`, `/health` `200`, Swagger `200`, ReDoc `200`,
authenticated Product read `200`, missing token `401`, and insufficient
permission `403`. The database is at `c7d8e9f0a1b2 (head)` and `alembic check`
reports no new upgrade operations.

## 7. Alembic graph and runtime migration proof

**CURRENT VERIFIED:** one linear graph contains 20 unique revision IDs, one
head, no branch, no missing parent, and no duplicate ID. Seven pre-sprint
revision files remain Git-tracked and unchanged. Thirteen additive sprint
revisions remain untracked because commit/push was forbidden.

| Filename | Revision | Down revision | Purpose | Sprint | Runtime proof |
|---|---|---|---|---:|---|
| `cea65f170298_initial_database_schema.py` | `cea65f170298` | `None` | Initial schema | no | **CURRENT VERIFIED** upgrade |
| `8b2f4d1c6a10_execution_core.py` | `8b2f4d1c6a10` | `cea65f170298` | Execution core | no | **CURRENT VERIFIED** upgrade |
| `d4a9c8e7f621_product_core_foundation.py` | `d4a9c8e7f621` | `8b2f4d1c6a10` | Product core foundation | no | **CURRENT VERIFIED** upgrade |
| `eb5f2829e72e_add_products_table.py` | `eb5f2829e72e` | `d4a9c8e7f621` | Canonical Products table | no | **CURRENT VERIFIED** upgrade |
| `f1a2b3c4d5e6_inventory_foundation.py` | `f1a2b3c4d5e6` | `eb5f2829e72e` | Warehouses and Inventory | no | **CURRENT VERIFIED** upgrade |
| `b2c3d4e5f6a7_inventory_movements.py` | `b2c3d4e5f6a7` | `f1a2b3c4d5e6` | Inventory movements | no | **CURRENT VERIFIED** upgrade |
| `c3d4e5f6a7b8_inventory_reservations.py` | `c3d4e5f6a7b8` | `b2c3d4e5f6a7` | Reservations/fulfillment | no | **CURRENT VERIFIED** upgrade |
| `d5e6f7a8b9c0_product_attribute_system.py` | `d5e6f7a8b9c0` | `c3d4e5f6a7b8` | Product Attribute system | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `e6f7a8b9c0d1_attribute_platform_completion.py` | `e6f7a8b9c0d1` | `d5e6f7a8b9c0` | Attribute platform completion | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `f7a8b9c0d1e2_product_content_platform.py` | `f7a8b9c0d1e2` | `e6f7a8b9c0d1` | Product Content platform | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `a8b9c0d1e2f3_product_content_completion.py` | `a8b9c0d1e2f3` | `f7a8b9c0d1e2` | Product Content completion | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `b9c0d1e2f3a4_content_template_conditions.py` | `b9c0d1e2f3a4` | `a8b9c0d1e2f3` | Template conditions | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `c0d1e2f3a4b5_product_content_quality.py` | `c0d1e2f3a4b5` | `b9c0d1e2f3a4` | Content quality/scoring | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `d1e2f3a4b5c6_product_content_invariants.py` | `d1e2f3a4b5c6` | `c0d1e2f3a4b5` | Current-revision invariants | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `e2f3a4b5c6d7_execution_job_leases.py` | `e2f3a4b5c6d7` | `d1e2f3a4b5c6` | Worker leases/fencing | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `f3a4b5c6d7e8_execution_job_query_indexes.py` | `f3a4b5c6d7e8` | `e2f3a4b5c6d7` | Job query/claim v2 indexes | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `f4a5b6c7d8e9_fix_execution_claim_priority_index.py` | `f4a5b6c7d8e9` | `f3a4b5c6d7e8` | Correct priority direction | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `a5b6c7d8e9f0_normalize_attribute_check_constraint_names.py` | `a5b6c7d8e9f0` | `f4a5b6c7d8e9` | Stable Attribute constraint names | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `b6c7d8e9f0a1_optimize_execution_claim_index.py` | `b6c7d8e9f0a1` | `a5b6c7d8e9f0` | Partial ASC claim v3 index | yes | **CURRENT VERIFIED** upgrade/downgrade |
| `c7d8e9f0a1b2_add_cursor_pagination_indexes.py` | `c7d8e9f0a1b2` | `b6c7d8e9f0a1` | Cursor pagination indexes | yes | **CURRENT VERIFIED** upgrade/downgrade |

Command results:

| Gate | Result |
|---|---|
| `alembic heads` | **CURRENT VERIFIED:** exactly `c7d8e9f0a1b2` |
| `alembic branches` | **CURRENT VERIFIED:** none |
| `alembic history` | **CURRENT VERIFIED:** one 20-revision chain |
| `alembic current` | **CURRENT VERIFIED:** head |
| `alembic check` | **CURRENT VERIFIED:** no drift |
| Tracked revision diff | **CURRENT VERIFIED:** 0 files |

Disposable PostgreSQL proof:

| Scenario | Result |
|---|---|
| Empty database to head | **CURRENT VERIFIED:** 20 revisions, 47 public tables including `alembic_version` |
| Populated `c3d4e5f6a7b8` to head | **CURRENT VERIFIED:** representative Catalog, Inventory, Execution, and Attribute data preserved |
| Downgrade sprint revisions | **CURRENT VERIFIED:** all 13 reversed individually to `c3d4e5f6a7b8` |
| Re-upgrade | **CURRENT VERIFIED:** all 13 reapplied to head |
| Preservation | **CURRENT VERIFIED:** IDs and values unchanged; Attribute fields backfilled; Inventory retained `17 on_hand / 3 reserved` |
| ORM agreement | **CURRENT VERIFIED:** 46 application metadata tables plus Alembic's table equal 47 public tables |
| Cleanup | **CURRENT VERIFIED:** disposable migration databases removed |

## 8. Static, architecture, and import validation

| Gate | Final result |
|---|---|
| Compile application, migrations, tests, scripts | **CURRENT VERIFIED:** pass |
| SQLAlchemy mapper configuration | **CURRENT VERIFIED:** pass, 46 mapped tables |
| Ruff lint | **CURRENT VERIFIED:** pass |
| Ruff format check | **CURRENT VERIFIED:** 193 files already formatted |
| Ruff C901 | **CURRENT VERIFIED:** pass |
| MyPy | **CURRENT VERIFIED:** success, 143 source files, 0 errors |
| `pip check` | **CURRENT VERIFIED:** no broken requirements |
| `git diff --check` | **CURRENT VERIFIED:** exit 0; only Git line-ending notices |
| Required top-level imports | **CURRENT VERIFIED:** pass |
| Import-cycle/dependency-direction tests | **CURRENT VERIFIED:** pass |
| Repository/transaction AST rules | **CURRENT VERIFIED:** pass |
| Duplicate Product/schema/route ownership | **CURRENT VERIFIED:** none |
| OpenAPI operation-ID check | **CURRENT VERIFIED:** 228 unique IDs |
| OpenAPI compatibility | **CURRENT VERIFIED:** additive, no removed operation |

## 9. Complete pytest evidence

**CURRENT VERIFIED:** collection is exactly 254 tests with no collection error.
There are no skips, xfails, unexplained warnings, or deselected mandatory tests.

| Mode | Seed/workers | Result | Time |
|---|---|---:|---:|
| Full serial | 4,182,083,906 | 254 passed | 31.25 s |
| Full randomized | 101 | 254 passed | 31.06 s |
| Full fixed | 424,242 | 254 passed | 31.12 s |
| Full randomized | 202 | 254 passed | 31.03 s |
| Full randomized | 303 | 254 passed | 30.92 s |
| Full randomized | 404 | 254 passed | 31.40 s |
| Full randomized | 505 | 254 passed | 31.76 s |
| Full xdist | 2 workers, load-file, 424,242 | 254 passed | 21.44 s |
| Full branch coverage | 777 | 254 passed | 41.81 s |
| Post-clean-build full serial | 424,242 | 254 passed | 28.57 s |
| Post-clean-build full xdist | 2 workers | 254 passed | 17.75 s |

The final two rows are consecutive complete green runs after the final
application/test source change and clean image build.

Focused suites:

| Suite | Result |
|---|---|
| Architecture, OpenAPI, authorization, pagination | **CURRENT VERIFIED:** 87 passed in 9.48 s |
| Worker, PostgreSQL races, failure injection, critical paths | **CURRENT VERIFIED:** 107 passed in 15.31 s |

## 10. Statement and branch coverage

**CURRENT VERIFIED:** combined Uvicorn-process and pytest-process coverage:
7,211/8,510 statements (84.74%), 833/1,414 branches (58.91%), and 81%
coverage.py combined display.

| Critical area | Statement coverage | Branch coverage | State |
|---|---:|---:|---|
| Security | 97.4% | 72/80 = 90.0% | **CURRENT VERIFIED** |
| Request middleware | 90.5% | 9/10 = 90.0% | **CURRENT VERIFIED** |
| Catalog mutation: Category/Product | 99.5% | 65/68 = 95.6% | **CURRENT VERIFIED** |
| Catalog repositories | 76.8% | 60.2% | **CURRENT VERIFIED** |
| Attribute definition/query/value | 78.9% | 46.6% | **CURRENT VERIFIED** |
| Attribute mutation/recalculation/formula | 100% | 57/58 = 98.3% | **CURRENT VERIFIED** |
| Inventory balance | 64.3% | 46.4% | **CURRENT VERIFIED** |
| Inventory movement | 68.1% | 42.5% | **CURRENT VERIFIED** |
| Inventory reservation/fulfillment | 100% | 53/54 = 98.1% | **CURRENT VERIFIED** |
| Product Content revision/rollback | 100% | 14/14 = 100% | **CURRENT VERIFIED** |
| Product Content reference | 68.2% | 40.0% | **CURRENT VERIFIED** |
| Product Content template/library/scoring | 76.7% | 38.6% | **CURRENT VERIFIED** |
| Execution repository | 189/193 = 97.9% | 36/42 = 85.7% | **CURRENT VERIFIED** |
| Execution worker | 97.7% | 22/24 = 91.7% | **CURRENT VERIFIED** |
| Execution handlers | 91.2% | 14/14 = 100% | **CURRENT VERIFIED** |

**CURRENT VERIFIED:** every mandatory corruption-sensitive threshold is met.
The lower percentages are concentrated in read helpers, optional query shapes,
and defensive branches; behavior suites separately cover atomic Catalog
mutation, Inventory balance/movement rollback, content reference protection,
and template/library/scoring invariants. No uncovered branch was identified as
capable of partial canonical mutation or stale finalization.

## 11. Cross-domain concurrency matrix

**CURRENT VERIFIED:** all named races use real PostgreSQL, independent sessions,
barriers/events, final-state assertions, and a post-conflict usability query.
Critical races execute at least ten repetitions. Expected losers receive a
stable domain/HTTP conflict rather than HTTP 500.

### Catalog

| Race | Exact invariant/result |
|---|---|
| Concurrent Product updates | One versioned winner; stale writer rejected; one coherent final Product |
| Product update vs deactivate | One winner; stale loser rejected; version and `is_active` match the winner |
| Restore vs uniqueness conflict | Existing unique owner retained; restore rejected with conflict |
| Category reorder/move | Optimistic fence selects one winner; no cycle, duplicate position, or lost move |

### Product Attributes

| Race | Exact invariant/result |
|---|---|
| Same-value concurrent write | One canonical current value; duplicate/stale path is idempotent or typed conflict |
| Bulk vs single write | Serialized winner; bulk is all-or-nothing; versions/history align |
| Write vs lock | Lock state and value follow the committed winner; loser cannot bypass lock |
| Write vs approval | One version transition; approval/history/event match canonical value |
| Recalculation vs write | Derived result corresponds to the committed source version |
| Formula graph update vs recalculation | No mixed graph version; stale calculation cannot overwrite |
| Derived-value race | One current derived value per Product/definition |
| Prompt activation race | Exactly one active prompt version |
| Template assignment race | Assignment uniqueness/order remains valid |

### Inventory

| Race | Exact invariant/result |
|---|---|
| Two reservations against limited stock | One bounded winner when capacity is insufficient; no oversell |
| Reservation vs fulfillment | Row-lock ordering preserves reservation/balance equality |
| Reservation vs release | Final reservation state and reserved quantity agree |
| Concurrent fulfillment | Fulfilled quantity never exceeds reserved quantity |
| Adjustment vs reservation | Serialized balance; available quantity never becomes invalid |
| Warehouse deactivation vs mutation | Mutation cannot commit against an invalid inactive winner |
| Stock-transfer ordering | Source/destination locks use deterministic ordering |
| Oversell prevention | Sum of active reservations never exceeds stock |
| Negative-balance prevention | Database/service predicates reject a negative result |
| Idempotent movement race | One movement/effect for one idempotency identity |
| Multi-product deadlock ordering | Both sessions finish without an application deadlock; balances remain coherent |

### Product Content

| Race | Exact invariant/result |
|---|---|
| Concurrent content revisions | One current revision; losing version is typed conflict |
| Concurrent SEO revisions | One current SEO revision |
| Concurrent Landing revisions | One current Landing revision |
| Revision vs rollback | One serialized lineage winner; no orphan revision |
| Rollback vs rollback | One canonical rollback result/current revision |
| Revision vs deactivation | Current/inactive state follows one versioned winner |
| Template reorder | Positions remain unique and deterministic |
| Clone vs modification | Clone is complete from one locked version or is rolled back |
| Library assignment vs deactivation | No active invalid reference survives |
| Scoring-history race | Each completed calculation is recorded once |
| Prompt activation | Exactly one active prompt |
| One-current-revision invariant | Partial unique constraints and service fencing hold |

### Execution

| Race | Exact invariant/result |
|---|---|
| Duplicate idempotent submission | Both callers resolve to one canonical Job |
| Simultaneous claim | One worker owns one lease/attempt |
| Heartbeat vs recovery | Valid heartbeat preserves ownership; stale lease recovery wins only after expiry |
| Recovery vs completion | One fenced transition; stale completion rejected |
| Cancellation vs completion | One terminal state; cancelled lease cannot finalize |
| Retry vs late completion | New attempt owns finalization; late old token rejected |
| Stale worker success/failure | Both stale terminal paths raise lease loss |
| Dead-letter transition | Exhausted retry enters `DEAD_LETTER` once |
| Duplicate invocation | Idempotency returns one Job and one attempt sequence |
| Listing during transition | Every page contains valid states/versions without duplicate rows |

## 12. Failure-injection matrix

**CURRENT VERIFIED:** deterministic hooks/injected collaborators verify:

| Injected point/failure | Final-state assertion |
|---|---|
| Before flush | No canonical mutation |
| After flush | Rollback removes flushed row/change |
| Before commit | No committed mutation/history/event |
| Commit failure | Rollback; session remains usable |
| After canonical mutation | No partial mutation on rollback |
| Before history | Canonical mutation rolls back |
| After history | Canonical mutation and history roll back together |
| Before event | Mutation/history/event remain atomic |
| After event | No false event survives rollback |
| Attribute recalculation | No partial derived-value set |
| Content rollback | No orphan/current-revision divergence |
| Template clone | No parent/child partial clone |
| Inventory reservation | No reservation/balance divergence |
| Fulfillment | No fulfillment/reserved divergence |
| Movement insert | No movement/balance divergence |
| Worker handler exception | Retry/failure state follows bounded policy |
| Handler side effect before finalization | Stable side-effect key; stale finalization rejected |
| Heartbeat failure | Lease treated as lost; handler cancelled |
| Stale recovery failure | Recovery transaction rolls back |
| Serialization failure | One atomic winner; loser session reusable |
| Constraint violation | Stable conflict and clean rollback |
| PostgreSQL deadlock | Loser rolls back; both sessions reusable |
| Lock timeout | No partial mutation or leaked transaction |
| Database connection termination | Uncommitted flush absent after reconnect |

**CURRENT VERIFIED:** no false event/history, orphan revision/template child,
reservation/balance or movement/balance divergence, stale finalization,
duplicate finalization marker, leaked transaction, or unusable session was
observed.

## 13. Restart, recovery, and operational exercises

| Exercise | Final result |
|---|---|
| Kill worker during 30-second synthetic handler | **CURRENT VERIFIED:** Job observed `RUNNING`, attempt 1, lease token, version 2 before SIGKILL |
| Lease expiry/stale recovery | **CURRENT VERIFIED:** recovery count 1; state `RETRYING`, attempt 1, lease cleared, version 3, one retry history row |
| Old worker finalization | **CURRENT VERIFIED:** old token rejected with `JobLeaseLostError`; replacement attempt 2 succeeded, version 5 |
| SIGTERM during three-second handler | **CURRENT VERIFIED:** graceful completion `SUCCEEDED`, attempt 1, lease cleared |
| SIGTERM before worker commit | **CURRENT VERIFIED:** PostgreSQL lock held before commit; worker stopped; Job remained `PENDING`, attempt 0, no lease/attempt |
| Rolling API restart | **CURRENT VERIFIED:** secondary API returned 200 before, during, and after primary restart |
| Restart all API instances | **CURRENT VERIFIED:** health returned 200 after start |
| Rolling worker restart | **CURRENT VERIFIED:** 40/40 jobs succeeded, all attempt 1, exactly 40 attempts |
| Redis restart | **CURRENT VERIFIED:** `PONG`; canonical Category remained readable/updateable and was cleaned |
| Authentication-key rotation | **CURRENT VERIFIED:** old-key token valid while configured as previous key |
| Previous-key removal | **CURRENT VERIFIED:** same token rejected with 401 |
| Dead-letter manual retry | **CURRENT VERIFIED:** attempt 1 dead-lettered; manual retry returned 200/`RETRYING`; attempt 2 succeeded; exact two-row history |
| PostgreSQL restart during active transaction | **CURRENT VERIFIED:** disposable server restart terminated client; uncommitted row count 0; new insert succeeded |
| Backup/restore to clean PostgreSQL | **CURRENT VERIFIED:** head/check clean; expected counts; zero orphan/duplicate/fencing/inventory invariant violations |

All disposable containers/databases and restart-specific rows were removed.
The standard Compose stack remains healthy.

## 14. Execution claim-index benchmark

**CURRENT VERIFIED:** the canonical claim query filters queue/claimable status
and `available_at`, orders
`priority ASC, created_at ASC, id ASC`, locks with
`FOR UPDATE SKIP LOCKED`, and limits to one row.

Reference workload: 100,000 Jobs, warmed PostgreSQL transaction.

| Index variant | Plan | Rows scanned | Execution | Buffers/temp |
|---|---|---:|---:|---|
| Old index | sequential scan + sort | 100,000 | 98.728 ms | 10,988 shared hits; 1,476 temp reads; 6,861 temp writes |
| Incorrect priority-DESC v2 | sequential scan + sort | 100,000 | 98.701 ms | full candidate scan and temp sort |
| Status-leading priority-ASC v2 | sequential scan + sort | 100,000 | 97.697 ms | full candidate scan and temp sort |
| Partial ASC `ix_jobs_claim_v3` | index scan, no sort | 1 | 0.018 ms | 16 shared hits; 0 temp |

**CURRENT VERIFIED:** planning time was below 0.1 ms for every variant; retained
exact endpoints are 0.096 ms for the old plan and 0.055 ms for v3. The v3 plan
had no sort or temporary I/O and did not block a competing `SKIP LOCKED`
claim. The benchmark transaction rolled back, leaving only the canonical v3
index state.

## 15. Cursor pagination benchmark

**CURRENT VERIFIED:** equivalent offset/keyset pages were compared at logical
depths 0, 1,000, 10,000, 50,000, and 99,000 where the dataset permitted.
Resolved Attributes used depths through 10,000 because its exact cardinality is
10,023.

Depth 99,000 (20 warmed samples, page size 100):

| Domain | Keyset avg/p95/p99 | Offset avg/p95/p99 | Rows scanned keyset/offset | Index | Payload | Queries |
|---|---:|---:|---:|---|---:|---:|
| Inventory | 2.222/2.280/2.325 ms | 7.188/7.610/7.753 ms | 100/99,100 | `ix_inventory_created_cursor` | 35,987 B | 2 |
| Jobs | 2.288/2.431/2.665 ms | 6.836/7.499/7.655 ms | 100/99,100 | `ix_jobs_created_cursor` | 60,828 B | 2 |
| Movements | 3.561/3.681/3.690 ms | 7.580/7.873/7.881 ms | 100/99,100 | `ix_inventory_movements_occurred_cursor` | 59,288 B | 2 |
| Products | 2.359/2.486/2.517 ms | 7.738/8.696/8.961 ms | 100/99,100 | `ix_products_created_cursor` | 38,090 B | 2 |
| Reservations | 2.434/2.541/2.615 ms | 8.432/8.742/8.802 ms | 100/99,100 | `ix_inventory_reservations_created` | 54,988 B | 2 |

Resolved Attributes at maximum available depth 10,000:

| Mode | Avg/p95/p99 | Rows scanned | Payload | Queries |
|---|---:|---:|---:|---:|
| Keyset | 0.560/0.641/0.728 ms | 23 | page-bounded | 2 |
| Offset | 2.116/2.348/2.389 ms | 10,023 | 32,612 B | 2 |

**CURRENT VERIFIED:** `EXPLAIN (ANALYZE, BUFFERS)` selected bounded cursor
indexes, used no temp sort on the keyset paths, and showed offset buffer/row
work growing with depth.

Complete traversal:

| Domain | Expected/seen | Pages | Duplicates | Skipped |
|---|---:|---:|---:|---:|
| Jobs | 100,000/100,000 | 1,000 | 0 | 0 |
| Inventory | 100,000/100,000 | 1,000 | 0 | 0 |
| Movements | 100,000/100,000 | 1,000 | 0 | 0 |
| Reservations | 100,000/100,000 | 1,000 | 0 | 0 |
| Products | 100,000/100,000 | 1,000 | 0 | 0 |
| Resolved Attributes | 10,023/10,023 | 101 | 0 | 0 |

**CURRENT VERIFIED:** cursors are signed, include a unique ID tie-breaker, reject
tampering, and are bound to sort/filter/snapshot parameters. A cursor cannot be
reused with changed filters or ordering.

## 16. Resolved-attribute benchmark at 10,023 definitions

**CURRENT VERIFIED:** the disposable dataset contains exactly 10,023 Attribute
Definitions with Product/category/global assignment mixtures, representative
values, groups, templates, scopes, and families.

| Workload | Avg | p95 | p99 | Payload | Peak memory | Queries |
|---|---:|---:|---:|---:|---:|---:|
| First ordinary page | 27.068 ms | 35.956 ms | 44.503 ms | 154,066 B | 1,396,158 B | 8 |
| Middle ordinary page | 31.549 ms | 32.165 ms | 32.167 ms | 196,530 B | 1,318,844 B | 7 |
| Final ordinary page | 13.943 ms | 14.335 ms | 14.420 ms | 45,335 B | 457,754 B | 7 |
| `include_unset=false` | 28.316 ms | 34.068 ms | 34.188 ms | 154,065 B | 1,400,230 B | 8 |
| Scope filter, 4,000 total | 32.813 ms | 40.632 ms | 49.010 ms | 196,529 B | page-bounded | 8 |
| Family filter, 1,000 total | 23.873 ms | 26.118 ms | 26.909 ms | 154,065 B | page-bounded | 8 |
| Template filter, 2,000 total | 26.531 ms | 35.460 ms | 44.901 ms | 154,065 B | page-bounded | 9 |

Streaming export:

| Metric | Result |
|---|---:|
| First byte | 87.225 ms |
| Complete export | 2,224.112 ms |
| Rows | 10,023 |
| Payload | 17,568,564 B |
| Peak memory | 11,047,280 B |
| Queries | 148 page-sized queries |

**CURRENT VERIFIED:** every ordinary page is below 1 MiB, average below 100 ms,
p95 below 200 ms, and page/materialization bounded. Export is intentionally
streaming and separate from the ordinary JSON route.

## 17. Worker throughput and correctness

**CURRENT VERIFIED:** `system.synthetic` provides controlled duration/failure
with no external effect. All scenarios preserve exact terminal counts; only the
retry workload retries (12), with 0 lease losses and 0 duplicate finalization
attempts.

Throughput and drain time:

| Workers | Fast jobs/s (drain) | Medium jobs/s (drain) | Retry jobs/s (drain) | Failing jobs/s | Long jobs/s (drain) | Peak DB connections |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 159.688 (0.626 s) | 17.014 (2.351 s) | 1.997 (6.010 s) | 150.034 | 0.658 (12.158 s) | 2 |
| 2 | 281.321 (0.355 s) | 32.316 (1.238 s) | 2.129 (5.637 s) | 241.655 | 1.312 (6.096 s) | 3 |
| 4 | 472.215 (0.212 s) | 64.436 (0.621 s) | 2.126 (5.645 s) | 388.197 | 2.615 (3.060 s) | 5 |

One-worker latency detail:

| Workload | Queue-to-worker-start p50/p95/p99 | Eligible-to-attempt-start p95 | Handler execution p95 |
|---|---:|---:|---:|
| Fast | 310.653/576.423/598.966 ms | 576.135 ms | 4.916 ms |
| Medium | 1,149.372/2,166.923/2,256.621 ms | 2,166.614 ms | 56.527 ms |
| Retry | 45.966/77.658/80.501 ms | 73.348 ms | 12.569 ms |
| Failing | 141.027/249.003/258.594 ms | bounded | 5.417 ms |
| Long/heartbeat | 5,321.986/10,100.428/10,525.199 ms | bounded | 1,509.015 ms |

**CURRENT VERIFIED:** fast, medium, failing, and heartbeat-long throughput scales
in the expected direction from one to two to four workers. Retry throughput
plateaus at the configured backoff rather than at claim capacity.

`Eligible-to-attempt-start` is measured from job creation (or retry
`available_at`) until the attempt starts. It includes polling interval,
scheduler, queue, transaction, and worker availability delay; it is not the SQL
claim query latency. The isolated indexed SQL claim query measured 0.018 ms in
the reference plan above.

## 18. Current OpenAPI and API contract matrix

Generated artifacts:

- [`openapi-normalized.json`](openapi-normalized.json)
- [`api-operation-matrix.json`](api-operation-matrix.json)
- [`request-boundary-inventory.json`](request-boundary-inventory.json)

**CURRENT VERIFIED:**

| Contract count | Current |
|---|---:|
| Paths | 157 |
| Operations | 228 |
| Schemas | 134 |
| Security schemes | 1 |
| Unique operation IDs | 228 |
| Duplicate operation IDs | 0 |
| Protected operations | 225 |
| Deliberately public operations | 3 |
| Request fields inventoried | 961 |
| Heuristic boundary-review candidates | 563 |

The three public operations are platform root/health surfaces. No business
mutation or business read is accidentally public.

**CURRENT VERIFIED:** all 225 protected operations were called without a token
and with an invalid token (450 requests), all returning 401. Role tests establish
403 for insufficient permission. The operation matrix records success schema,
401, 403, validation, not-found, conflict where applicable, parameters,
request boundaries, pagination mode, structured errors, and stable operation
ID.

Compared with the contract baseline of 152 paths/223 operations, the current
contract is additive by exactly five paths/operations:

```text
/api/v1/catalog/products/{product_id}/attributes/resolved
/api/v1/catalog/products/{product_id}/attributes/resolved/export
/api/v1/jobs/{job_id}/cancel
/api/v1/jobs/{job_id}/retry
/api/v1/metrics
```

Schema and security-scheme counts remain 134 and 1.

## 19. Dependency advisory status

**CURRENT VERIFIED:** dependencies are exact-pinned in
`backend/requirements.lock`; SHA-256 and `pip check` are recorded above.

**NOT VERIFIED:** the external advisory command

```text
docker compose run --rm api pip-audit -r requirements.lock
```

was not permitted to access/execute the remote advisory workflow in this
environment. No vulnerability-free claim is made.

Required release-time command:

```text
pip-audit -r backend/requirements.lock
```

Any compatible lock upgrade triggered by that scan must be followed by the
same static, Alembic, full pytest, and image-build gates.

## 20. Accepted non-blocking debt and remaining risks

| Item | State | Treatment |
|---|---|---|
| Global branch coverage below critical-path percentages | **CURRENT VERIFIED** | Retain targeted behavior coverage; do not add meaningless getter tests |
| Offset pagination compatibility | **CURRENT VERIFIED** | Supported for clients; signed keyset is recommended for deep traversal |
| Process-local rate limit/metrics in horizontally scaled deployment | **CURRENT VERIFIED** | Documented architecture exception; use a shared backend before internet-scale exposure |
| External OIDC/JWKS integration | **CURRENT VERIFIED** | Optional for internal deployment; current issuer/audience/key rotation/role model is enforced |
| 563 heuristic request-boundary review candidates | **CURRENT VERIFIED** | Inventory, not 563 defects; enforce stricter limits as each business contract requires |
| 236-entry uncommitted working tree | **CURRENT VERIFIED** | Deliberately preserved; requires human review and a controlled commit sequence |
| External vulnerability advisory | **NOT VERIFIED** | Mandatory release-time scan above |
| Host `.venv` | **NOT VERIFIED** | Recreate only after Python 3.12 is installed; Docker remains authoritative |

## 21. Final freeze statement

**CURRENT VERIFIED:** all locally executable mandatory Foundation work is
complete against the current application/test source and final clean-built
images. Migration deployment, transaction safety, concurrency, restart
recovery, query bounds, claim fencing, worker scaling, authentication, and API
contract gates pass.

## GO FOR CHAPTER 3 — FOUNDATION FROZEN

No commit or push was performed.
