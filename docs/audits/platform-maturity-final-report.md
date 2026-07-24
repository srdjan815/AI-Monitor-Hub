# Platform Maturity Sprint — Final Engineering Report

> Historical pre-freeze report. Its `NO GO` decision and open-gap list were
> inputs to later Foundation work and are superseded by
> [post-freeze-repository-release-final-report.md](post-freeze-repository-release-final-report.md).

## Executive decision

**NO GO FOR CHAPTER 3**

The platform made measurable progress: MyPy is clean, reproducible QA tooling
is locked, coverage/random/parallel runs pass, an isolated 251,000-row
performance dataset was exercised, and Execution claim latency was reduced from
15.317 ms to 0.076 ms with a corrective migration. The foundation is not ready
to freeze because the resolved Product Attribute endpoint is unbounded, critical
service/worker paths have low or zero coverage, large god classes remain, and
the requested cross-domain concurrency and destructive recovery matrices are
not complete.

## Repository and architecture statistics

The measured Python scope contains 113 application/test files and 20,796 lines.
The current OpenAPI contains 152 paths, 223 operations, 133 schemas, one bearer
security scheme, and no duplicate operation IDs.

Largest files:

| File | LOC | Direct imports |
|---|---:|---:|
| `product_content/services.py` | 1,094 | 16 |
| `inventory/service.py` | 1,071 | 12 |
| `catalog/platform_service.py` | 943 | 19 |
| `catalog/attribute_service.py` | 880 | 17 |
| `catalog/routers/product_attributes.py` | 761 | 14 |
| `catalog/service.py` | 751 | 10 |
| `product_content/repositories.py` | 654 | 9 |
| `catalog/repository.py` | 478 | 6 |
| `inventory/repository.py` | 440 | 7 |

Largest classes:

| Class | LOC | Public/all methods | Decision |
|---|---:|---:|---|
| `InventoryService` | 1,040 | 17/38 | SPLIT |
| `AttributePlatformService` | 892 | 36/43 | SPLIT |
| `ProductAttributeService` | 822 | 27/36 | SPLIT |
| `CatalogService` | 725 | 15/22 | SPLIT |
| `ContentRepository` | 619 | 45/46 | SPLIT |
| `CatalogRepository` | 462 | 32/33 | SPLIT |
| `InventoryRepository` | 423 | 31/32 | SPLIT |
| `ProductAttributeRepository` | 371 | 24/25 | SPLIT |

These classes have multiple independent transaction/query reasons to change.
Splitting them safely requires compatibility façades plus additional transaction
and concurrency coverage. Performing that extraction without those proofs would
increase rather than reduce freeze risk, so it remains a HIGH blocker.

## Module and dependency graph

The enforced direction is:

`API router -> service/coordinator -> repository -> SQLAlchemy -> PostgreSQL`

Catalog owns Product. Inventory and Product Content reference it. Attribute
mutations enter `AttributeMutationCoordinator`; injected recalculation removes
the former local-import service cycle. Execution handlers use repository leases
and fenced finalization. Architecture tests reject SQL or transaction control in
routers, FastAPI errors or commits in repositories, unprotected routes,
duplicate Product ownership, and the former Attribute cycle.

## Static analysis and complexity

| Gate | Before | After |
|---|---:|---:|
| MyPy | 105 errors / 20 files | **0 / 91 source files** |
| Ruff | pass | pass |
| Ruff C901 | failures at 39 and 13 | pass |
| Python compilation | pass | pass |
| SQLAlchemy mapper configuration | pass | pass |

MyPy was fixed through generic repository/service return types, precise
SQLAlchemy result handling, Optional narrowing, ORM-to-Pydantic conversion, and
typed collections. No global ignore was added. `mypy-baseline.json` now requires
zero errors and the collected static test fails on any regression.

## Test and coverage report

| Run | Result |
|---|---|
| Normal randomized full suite | 111/111 passed |
| Fixed seed `1742026` | 111/111 passed |
| Parallel `xdist -n 2 --dist=loadfile` | 111/111 passed |
| Branch coverage suite | 111/111 passed |
| Execution PostgreSQL concurrency, five repetitions | 10/10 passed |
| Skips | 0 |

Coverage is 57% over 6,764 statements and 1,022 branches. Security is 90%,
errors 92%, and request middleware 81%. Execution worker and handlers are 0%;
Attribute and platform services are 13%; Inventory service/repository are
20–21%; Catalog service/repository are 26–27%; Product Content services are 34%.
This is insufficient critical-path coverage for a foundation freeze.

## Performance dataset and query report

A disposable PostgreSQL database was migrated from empty to head and loaded
with generated data only:

| Entity | Rows |
|---|---:|
| Products | 1,000 |
| Attribute definitions | 10,023 |
| Product attribute values | 50,000 |
| Content revisions | 500 |
| Languages | 20 |
| Warehouses | 100 |
| Inventory | 100,000 |
| Execution jobs | 100,000 |

It was analyzed, used for `EXPLAIN (ANALYZE, BUFFERS)`, exercised through a
disposable ASGI process, downgrade/upgraded, and deleted.

| Query | Execution | Plan observation |
|---|---:|---|
| Product page at offset 900 | 0.654 ms | 1k seq scan + memory sort |
| 50 product attribute values | 0.262 ms | bitmap product index |
| Inventory by product, 100 | 0.491 ms | bitmap composite index |
| Inventory by warehouse, 100 | 0.215 ms | bitmap index + top-N |
| Content current, 100 | 0.431 ms | 500-row seq scan + top-N |
| Job claim before correction | 15.317 ms | scans/sorts 10,001 candidates |
| Job claim after correction | **0.076 ms** | direct v2 index scan |
| Jobs offset 99,000 before | 84.818 ms | external merge and temp files |
| Jobs offset 99,000 after | 30.629 ms | index, still walks 99,100 rows |

Corrective migration `f3a4b5c6d7e8` adds claim and stable-list indexes. Its
downgrade/re-upgrade passes. Deep offset remains linear and needs additive cursor
pagination.

Thirty-request ASGI samples include response serialization:

| Endpoint | Average | p95 | Payload |
|---|---:|---:|---:|
| Products 500 | 9.57 ms | 45.27 ms | 168 KB |
| Attributes 1,000 | 40.29 ms | 135.59 ms | 450 KB |
| Resolved attributes for one product | **421.09 ms** | **500.78 ms** | **12.66 MB** |
| Inventory by product, 100 | 4.30 ms | 19.99 ms | 37 KB |
| Jobs 100 | 26.86 ms | 33.91 ms | 55 KB |
| Content search 100 | 18.28 ms | 181.97 ms | 97 KB |

The worst endpoint materializes all 10k global definitions and is
CPU/serialization bound. It requires a bounded pageable response or a separate
export contract. This HIGH defect blocks freeze.

## Database and migration report

Alembic has one head: `f3a4b5c6d7e8`. Current equals head and autogenerate finds
no drift. Empty-to-head succeeded. The new revision downgrade/re-upgrade
succeeded. No previous migration was edited. Mapper configuration is clean.

## Execution, concurrency, and recovery

Claim assigns worker, attempt, and random lease token. Heartbeat and finalization
compare ID, RUNNING status, worker, attempt, and lease. Recovery replaces the
lease and fences stale completion. Five repeated real-PostgreSQL races prove
idempotent submission and stale-worker rejection.

Not proven: cancellation, external-side-effect idempotency, simultaneous
inventory reservation/fulfillment, formula recalculation races, revision races,
Redis/PostgreSQL restart during work, SIGTERM at each transaction phase, and
deadlock retry policy. These are HIGH blockers.

## Security and attack report

Executed tests cover missing token, malformed signature, expired token,
insufficient permission, allowed principals, seed administration, raw-preview
double gating, oversized bodies, request correlation, insecure production
settings, and representative privileged route families. All non-health routes
carry authentication and OpenAPI bearer metadata.

Remaining limitations are HMAC rotation/revocation/issuer/audience, no rate
limiting, and no complete replay/JTI defense. These block untrusted Internet
exposure.

## Request limits and API contract

Transport input is capped at 2 MiB. Major Content, prompt, description, note, and
JSON fields have schema limits. The sprint did not produce a machine-verified
row for every field or all exact/one-over/Unicode/deep/array/compressed cases.
Responses are not capped, demonstrated by the 12.66 MB attribute response.

OpenAPI snapshot, paths, operation IDs, security metadata, and structured error
responses pass. The index migration changes no HTTP contract. A complete
all-endpoint valid/invalid/401/403/404/409 matrix remains incomplete.

## Dependency and Docker report

pytest-cov 7.1.0, pytest-randomly 4.1.0, pytest-xdist 3.8.0, pip-audit 2.10.1,
types-bleach, and transitive dependencies are locked. API and worker images
build. `pip check` passes. Advisory lookup was not executed because it requires
separately authorized transmission of dependency metadata to an external
service; it is not reported as clean.

## Remaining issues, ordered

| Priority | Severity | Evidence | Required action | Blocks |
|---:|---|---|---|---|
| 1 | HIGH | Resolved attributes: 12.66 MB, 421 ms avg | bounded page/cursor or export | yes |
| 2 | HIGH | Worker and handlers 0% coverage | lifecycle/failure tests | yes |
| 3 | HIGH | Critical services 13–34% coverage | integration/failure matrices | yes |
| 4 | HIGH | Service classes 725–1,040 LOC | responsibility split with façades | yes |
| 5 | HIGH | Cross-domain race matrix absent | independent-session stress | yes |
| 6 | HIGH | Restart/SIGTERM/network matrix absent | disposable fault environment | yes |
| 7 | MEDIUM | Offset 99k walks 99.1k rows | cursor pagination | before scale |
| 8 | MEDIUM | Overall branch coverage 57% | critical branch thresholds | yes |
| 9 | MEDIUM | Advisory result unavailable | authorize locked scanner | yes |
| 10 | MEDIUM | No rate limiting | gateway/application policy | before Internet |
| 11 | MEDIUM | Shared-secret lifecycle | external issuer and key rotation | before Internet |
| 12 | LOW | Original claim index remains beside v2 | later measured cleanup migration | no |

## Accepted technical debt

Compatibility service/repository modules remain public import façades. Offset
pagination remains for backward compatibility while cursor pagination is
designed additively. Sequential scans on 500–1,000-row tables are currently
efficient. Final fencing protects database state even though heartbeat loss
does not immediately cancel handler execution; external handlers must remain
idempotent.

## Final reasoning

Security, static typing, lint, mapper, migration, reproducible build, standard
tests, randomized order, parallel tests, and Execution claim behavior are
strong. The unbounded attribute response, zero worker coverage, weak critical
service coverage, incomplete concurrency/failure matrices, and unresolved god
classes are direct evidence against a ten-year foundation freeze.

**NO GO FOR CHAPTER 3**
