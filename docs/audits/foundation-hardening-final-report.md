# Foundation Hardening Final Report

> Historical hardening checkpoint. The later
> `platform-maturity-final-report.md` supersedes its MyPy, coverage, tooling,
> migration-head, and performance results.

## 1. Executive verdict

**NO-GO FOR CHAPTER 3.** Critical unauthenticated mutation exposure, Catalog
router SQL, the hidden Attribute service cycle, and stale Execution finalization
were corrected and covered. The baseline is materially safer, but mandatory
coverage, randomized/parallel execution, complete concurrency and
failure-injection matrices, downgrade proof, advisory scanning, performance
plans, comprehensive domain field boundaries, rate limiting, and god-class
decomposition are incomplete.

## 2. Initial state and confirmed findings

The pre-change inventory contained 153 files, 121 Python files, approximately
21,700 lines, 152 OpenAPI paths, 223 operations, 134 schemas, and no duplicate
operation IDs. Alembic was clean at `d1e2f3a4b5c6`. Ninety-three tests passed
twice. Ruff passed; C901 reported complexity 39 in attribute normalization and
13 in inventory fulfillment. MyPy reported 105 errors in 20 files.

Confirmed findings are catalogued as FH-001 through FH-016 in the pre-change
report. The highest-impact causes were router-level global protection being
absent, permissive production defaults, no request ceiling, SQL in Catalog
routers, a local-import service cycle, no worker fencing, and non-unique list
ordering.

## 3. Corrections

- Added signed expiring principals, centralized roles/permissions, protected
  router inclusion, OpenAPI bearer security, actor propagation, and security
  regression tests.
- Added production startup validation, explicit CORS/hosts/docs policy, removed
  Compose reload, and documented remaining proxy/rate-limit assumptions.
- Added a 2 MiB transport limit and domain limits for principal Product Content,
  Inventory, and Execution payloads.
- Centralized request IDs and structured error codes while retaining `detail`.
- Moved Catalog dashboard/formula/dependency/prompt SQL into repositories and
  services; architecture AST tests prevent recurrence.
- Added `AttributeMutationCoordinator` and callback injection, removing the
  ProductAttributeService local-import cycle.
- Refactored the two reported C901 hotspots; application C901 is clean.
- Added deterministic UUID tie-break ordering to Catalog, Attribute, Inventory,
  and Execution lists.
- Added Execution lease token migration, heartbeat CAS, attempt/token fencing,
  stale recovery protection, and two real-PostgreSQL integration tests.
- Added exact dependency constraints and a MyPy zero-growth baseline.
- Standardized pytest on one session event loop, eliminating cross-loop use of
  the application async connection pool.

## 4. Authentication and authorization

Health alone is public. All other registered route families depend on
`authorize_request`; an architecture test checks the route graph. Missing or
invalid tokens return 401, insufficient permissions return 403, and allowed
requests proceed to validation/business behavior. Seed is protected. Raw preview
requires both explicit permission and the server flag. Current HMAC tokens lack
issuer/audience, revocation, rotation, and external identity-provider issuance;
this is a high operational limitation before external deployment.

## 5. Database, concurrency, and failure evidence

Alembic has one head, current equals head, and autogenerate reports no drift. A
fresh disposable PostgreSQL database upgraded from empty through all 15
revisions to `e2f3a4b5c6d7`. Existing old revisions were not edited.

Execution concurrency: 2 scenarios passed in each of 5 repetitions (10/10):
concurrent idempotent submit converged on one job; stale worker finalization
after recovery was fenced. Existing transaction tests cover selected Catalog and
Inventory rollback paths. The requested cross-module concurrency and exhaustive
failure-injection matrices were not completed; they block Chapter 3.

## 6. API and quality evidence

The current collected suite is 111/111 passing with no skips. Security and
architecture focus is 23/23. Ruff and Ruff C901 pass. Python compilation and
SQLAlchemy mapper configuration pass. `pip check` and `git diff --check` pass.
Product Content OpenAPI snapshot intentionally changed for bearer security,
structured default error responses, and field constraints and now passes. MyPy
improved from 105 errors/20 files to a reviewed zero-growth ceiling of 103/19;
it is not clean.

API, PostgreSQL, and Redis containers are healthy; the worker is running.
Because xdist, randomized-order, coverage, and advisory tools are absent from
the built image, those gates were not executed.

The hardened API and worker images build successfully from the pinned
constraints. The running stack was deliberately not restarted as part of the
final build proof. Final OpenAPI generation reports 152 paths, 223 operations,
133 component schemas, one `BearerAuth` security scheme, and zero duplicate
operation IDs.

## 7. Compatibility and decomposition

Public paths, request model names, operation IDs, and normal `detail` error
content were preserved. Existing monolithic `CatalogService`,
`CatalogRepository`, `InventoryService`, `InventoryRepository`, and Product
Content service/repository façades remain. Moving persistence and orchestration
concerns reduced coupling, but measured physical god-class decomposition was not
completed. This is an architecture-gate blocker, not a false positive.

## 8. Remaining issues

| Severity | Area | Reproduction/evidence | Impact | Required action | Blocks Chapter 3 |
|---|---|---|---|---|---|
| High | Testing | pytest-cov/xdist/randomly absent | Unknown coverage/flakiness | lock tools; branch coverage; parallel/random runs | yes |
| High | Concurrency | only Execution matrix repeated | Supplier/stock races unproven | implement full independent-session matrix | yes |
| High | Failure recovery | exhaustive injection suite absent | partial-state risk unproven | inject flush/commit/recalc/handler failures | yes |
| High | Performance | no 1k dataset or EXPLAIN ANALYZE | N+1/query-plan risk | add query budgets and plan review | yes |
| High | Request limits | not every Catalog/JSON/result field has exact/Unicode/deep boundary tests | resource exhaustion gaps | inventory all fields and add boundary suite | yes |
| High | Architecture | god-class decomposition/measurements incomplete | Chapter 3 coupling cost | split by real transaction/query responsibilities with façades | yes |
| Medium | IAM | no issuer/audience/revocation/key rotation | weak operational lifecycle | integrate trusted issuer and rotation | before external exposure |
| Medium | Operations | no rate limiter | brute-force/DoS exposure | add gateway/app policy | before external exposure |
| Medium | Migrations | downgrade not run | rollback path unproven | disposable downgrade/upgrade test | yes |
| Medium | Dependencies | no advisory scan | known-vulnerability status unknown | run locked advisory scanner | yes |
| Medium | Types | 103 MyPy errors in 19 files | static blind spots | burn down baseline, starting transaction DTOs | no under current zero-growth policy |
| Low | Worker | heartbeat loss does not cancel handler immediately | wasted work/external side effects | cooperative cancellation and idempotent handlers | no with fencing |

## 9. False positives and non-findings

The canonical Product is not duplicated by Inventory or Product Content.
OpenAPI had no duplicate operation IDs. Alembic had no drift. Repository commits
were not found by architecture enforcement. The two transient authorized-route
500s observed while adding tests were not business failures: pytest used a
global async engine across function-scoped event loops. A session-scoped loop
fixed the reproducible cross-loop pool error and the protected paths now return
their intended responses.

## 10. Files and artifacts

The complete inspected scope was `backend/app`, `backend/tests`,
`backend/alembic`, backend configuration, Docker/Compose, environment examples,
and related documentation. The exact working-tree inventory must be taken from
`git status --short`; no commit or push was performed. One corrective migration
was added by this sprint: `e2f3a4b5c6d7_execution_job_leases.py`.

Detailed policies:

- `docs/audits/foundation-hardening-prechange-findings.md`
- `docs/architecture/platform-foundation.md`
- `docs/architecture/security-architecture.md`
- `docs/architecture/attribute-orchestration.md`
- `docs/architecture/execution-worker-leases.md`
- `docs/security/api-authorization-matrix.md`
- `docs/security/production-configuration.md`
- `docs/operations/dependency-management.md`
- `docs/operations/migrations.md`
- `docs/operations/testing-strategy.md`

## 11. Gate decision

Security, core router boundaries, database head/drift/bootstrap, worker fencing,
basic API contract, Ruff/C901, compilation, mapper, and standard test gates pass.
Mandatory G, H, parts of B/C/F, and operational security remain incomplete.
Therefore the only evidence-supported verdict is **NO-GO FOR CHAPTER 3**.
