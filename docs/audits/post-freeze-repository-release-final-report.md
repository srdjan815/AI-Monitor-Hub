# Post-freeze repository and release closure

## Scope and verdict gate

This report closes the Foundation repository, dependency, development
environment, multi-instance, request-boundary, and release-hygiene sprint.
Supplier Platform and all Chapter 3 implementation remain out of scope.

The recoverable pre-change checkpoint was created before this sprint changed
the working tree. The verified archive is stored outside Git under
`%LOCALAPPDATA%\Temp\AI-Monitor-Hub-post-freeze-20260724T151925`:

- archive: `AI-Monitor-Hub-working-tree.zip`;
- entries: 312;
- size: 554,113 bytes;
- SHA-256:
  `248145BA20BA246A114F5C936FEF24FB2C5C2D98D193162E567449690BA8C7BE`;
- forbidden checkpoint entries: zero;
- read-back verification: passed.

The checkpoint details and per-file hashes are recorded in
`post-freeze-pre-git-checkpoint.md`.

## Repository and commit closure

The entry state on branch `feature/product-core` contained 47 tracked modified
files, 189 untracked nonignored files, and no staged files. All Git-visible
files were classified individually. The generated classification and redacted
secret report are the authoritative final inventories.

Controlled commits:

| Commit | Message | Files | Gate before commit |
|---|---|---:|---|
| `11762e5` | `feat(foundation): version frozen application platform` | 209 | full serial, five seeds, xdist, branch coverage, static, migration, Docker, multi-instance, secret and staged-diff gates passed |
| `5c707fc` | `docs: freeze foundation architecture and operations` | 60 | documentation, link, machine-path and release-evidence gates passed |
| `d63d47d` | `test: remove local database assumptions` | 7 | clean-database integration failures reproduced and corrected |
| `39c0913` | `fix(config): accept compose-only environment values` | 2 | `.env.example` copied verbatim, focused regression and clean-clone suite passed |

The final release-evidence commit is resolved by the local annotated
`foundation-v1.0` tag; a commit cannot truthfully contain its own hash.

No remote commit or tag is pushed by this sprint.

## Cross-platform Python and dependency evidence

| Evidence | Windows | Docker/Linux |
|---|---|---|
| Interpreter | CPython 3.12.10, 64-bit | CPython 3.12.13 |
| pip | 26.1.2 | 26.1.2 |
| Exact lock install | PASS | PASS, clean no-cache image |
| `pip check` | PASS | PASS |
| `pip-audit` | PASS, zero known vulnerabilities | PASS, zero known vulnerabilities |
| Mapper configuration | 46 tables | 46 tables |
| `uvloop` | intentionally omitted by PEP 508 marker | 0.22.1 importable |
| Platform package | `colorama==0.4.6` | `uvloop==0.22.1` |

After excluding only those two reviewed platform markers, all 82 installed
packages have identical Windows and Linux versions. The final lock contains 81
nonblank, exactly pinned entries and has SHA-256:

```text
6DC94A09053D4143D7EA73AB696EC25E890733019DEFA0D6039FCF7ABDA83F24
```

The advisory source was the default PyPI vulnerability service used by
`pip-audit` 2.10.1 on 2026-07-24. No advisory is suppressed. Black and pytest
advisories discovered during the sprint were remediated with the smallest
reviewed compatible targets documented in
`../security/dependency-advisory-report.md`.

## Static, test, and runtime gates

| Gate | Final result |
|---|---|
| No-write Python compilation | PASS, 218 files |
| SQLAlchemy mapper configuration | PASS, 46 tables |
| Ruff | PASS |
| Ruff format | PASS, 198 files |
| Ruff C901 | PASS |
| MyPy | PASS, 143 application files |
| Full serial pytest | 288 passed in 84.53 s |
| Fixed post-build serial | 288 passed in 90.67 s |
| Seeds 101/202/303/404/505 | 288 passed for every seed |
| xdist, 2 workers, load-file | 288 passed in 46.90 s |
| Post-build xdist | 288 passed in 51.36 s |
| Branch-coverage run, seed 777 | 288 passed in 176.28 s |
| Clean-clone Linux suite | 289 passed, fresh database and no-cache image |
| Skips / xfails | zero |
| API health / protected auth | 200 / 401 without credentials / 200 with admin token |
| Swagger | 200 in the development profile |
| API and worker unhandled log errors after final restart | zero |
| Running workers | two |

The single pytest-process coverage run measured:

- 6,544/8,773 statements, 74.59%;
- 717/1,496 branches, 47.93%;
- 70.71% combined coverage.py score.

This isolated number does not instrument the separately running Uvicorn
process. Critical mutation, concurrency, corruption, authorization, and
failure paths have dedicated behavior suites; the lower global result remains
non-blocking test-depth debt rather than a hidden baseline.

## API contract and request boundaries

The normalized OpenAPI contract is deterministic across consecutive
regenerations:

- operations: 228;
- total inventoried fields: 1,196;
- request-reachable fields: 720;
- response-only fields: 476;
- query parameters: 235;
- high-risk review candidates: zero;
- medium-risk review candidates: zero;
- normalized OpenAPI SHA-256:
  `D76C859198C354DCD6FA7650D8A6BDCC1E19F269E1AF1D064CB133F864226B6C`;
- live minified OpenAPI SHA-256:
  `CB6BA16BF150627516E85B7A5FAF1B9353FA5C03BAF9718FA81250B916ADB876`.

Structural JSON limits cover encoded bytes, depth, nodes, keys, key length, and
array size. Public text, regex, cursor, collection, integer, decimal, bulk, and
legacy offset inputs have finite reviewed limits. User regex execution has a
hard timeout.

## Migration evidence

The chain contains 20 linear revisions and one head:
`c7d8e9f0a1b2`. All migration hashes match the external pre-change checkpoint;
no applied revision was edited during this sprint.

Disposable database evidence:

- empty database: base to head passed;
- head to `c3d4e5f6a7b8` and back to head passed;
- latest revision downgrade to `b6c7d8e9f0a1` and re-upgrade passed;
- populated `c3d4e5f6a7b8` database upgraded to head with one synthetic Category,
  Product, Warehouse, Inventory, and Job row preserved;
- `alembic check`: no new upgrade operations;
- disposable databases were target-verified and removed after the proof.

## Docker and multi-instance evidence

The final no-cache images are:

| Component | Image ID |
|---|---|
| API | `0f7d058f73a3e2e9ed94272b0e47ac601a82bf93910b37dea9cb90017134c612` |
| worker | `17a839434d0397e10729ba178c1b52771c3ca99b19bc79b2ca6ee5b13b08a27e` |
| PostgreSQL 15.18 | `74e110c41804365e3915fcc09d5e7a1eff50161aaa94d5da0e58e0cd75ae509c` |
| Redis 7.4.9 | `6ab0b6e7381779332f97b8ca76193e45b0756f38d4c0dcda72dbb3c32061ab99` |

Base and two-replica Compose normalization pass. The final runtime contains a
healthy API, healthy PostgreSQL and Redis, and two worker processes.

Two real API replicas shared one Redis fixed-window budget. Alternating one
actor across both replicas produced 30 application 422 responses followed by
one shared 429 with `Retry-After: 60`. With Redis stopped, both replicas
returned fail-closed 503 with `Retry-After: 1` and a CORS response header.
After Redis restarted healthy, the same mutation path reached the application
again with 422. Each replica exposed valid per-process Prometheus metrics.
Redis remains non-canonical and contains no domain state or raw identity.

## Git and sensitive-data evidence

The deterministic release inventory covers the exact union of tracked and
untracked nonignored files and includes itself. It uses NUL-delimited Git path
enumeration, handles spaces, records import and migration references, detects
content duplicates, and validates every required CSV field.

The secret scan records only rule names and truncated SHA-256 fingerprints.
It found zero review-required findings and no binary or unreadable Git-visible
path. Synthetic credentials are explicitly marked test/example literals.
`.env`, virtual environments, caches, coverage, dumps, logs, archives, and
local volumes are ignored. No Git-visible path contains a local absolute
machine path.

No source, migration, test, required contract artifact, or compatibility
facade was deleted. Only two disposable migration-proof databases and the two
temporary replica containers created by this sprint were removed.

## Reproducibility from Git alone

A `--no-local` clone was created at
`%LOCALAPPDATA%\Temp\AI-Monitor-Hub-foundation-repro-20260724T205000` and
advanced only through Git fetch plus fast-forward merge. No source file was
copied from the working repository. The tracked source/test/migration/config
manifest at `39c0913d946e8cdc296f6236d2ebfab2a230f174` has aggregate SHA-256
`DB4C0AED5645F5880F177701D8FDC29D33CAE999A516988FD91268E7AC156340`
in both repositories.

The clone used a new Windows CPython 3.12.10 virtual environment and an exact
lock installation. Windows Ruff, format, C901, MyPy, `pip check`, and
`pip-audit` passed. An isolated Compose project built API and worker images
without cache, created new PostgreSQL and Redis volumes, upgraded an empty
database through all 20 revisions, and reached a healthy API. Running the
suite inside that clean API image collected and passed all 289 tests. The
clone OpenAPI hash, migration head, 46-table mapper count, and lock hash match
the primary repository.

Clean-clone image IDs:

- API:
  `2e59444cf7f3fe72c63310c1f5cee9ac1c724e79ef6df8fa32ddf529384b0bae`;
- worker:
  `a682da34918a0f5e0c999f6f319241d1908e8655b2e2de9c28a7b6617f193a92`.

The proof also found and fixed two genuine portability defects: direct
integration tests no longer assume one hard-coded database, and Pydantic
settings now tolerate Compose-only values documented in `.env.example`.

## Twenty-category scorecard

| # | Category | Score | Evidence |
|---:|---|---:|---|
| 1 | Architecture | 10.0 | frozen module boundaries and decomposition suites pass |
| 2 | Correctness | 10.0 | complete serial, randomized, parallel and API behavior suites pass |
| 3 | Transaction safety | 10.0 | flush/commit ownership and rollback failure tests pass |
| 4 | Concurrency | 10.0 | PostgreSQL race, optimistic version and two-worker suites pass |
| 5 | Failure recovery | 10.0 | DB injection, lease fencing, Redis restart and worker recovery pass |
| 6 | Performance | 9.8 | indexed and cursor architecture is proven; historical benchmark numbers were not remeasured in this hygiene sprint |
| 7 | Security | 9.8 | auth, permission, request-size, regex, headers and shared limiting pass; external identity-provider integration remains optional |
| 8 | Dependency security | 10.0 | host/container audits are clean and parity is exact |
| 9 | Test quality | 9.5 | critical suites are deep; global isolated branch coverage remains 47.93% |
| 10 | Static typing | 10.0 | strict project MyPy gate is clean with zero baseline errors |
| 11 | API contract | 10.0 | deterministic 228-operation contract and zero boundary candidates |
| 12 | Migration safety | 10.0 | hash, empty, populated, downgrade/re-upgrade and drift proofs pass |
| 13 | Observability | 9.8 | bounded structured logs and per-replica metrics pass; aggregation is external infrastructure |
| 14 | Horizontal scaling | 9.8 | shared limiter and two replicas pass; Redis HA and Prometheus deployment are external |
| 15 | Git hygiene | 10.0 | exhaustive classification, ignore policy, staging and secret gates pass |
| 16 | Reproducibility | 10.0 | Git-only clone, exact Windows install, clean no-cache images, empty migration and 289-test proof pass |
| 17 | Windows development | 10.0 | supported CPython, exact install, VS Code, static and audit gates pass |
| 18 | Docker/Linux deployment | 10.0 | pinned clean images, parity, health and two workers pass |
| 19 | Documentation | 9.5 | onboarding and operations are complete; repository declares MIT but still needs owner-approved root license text before public distribution |
| 20 | Release readiness | 10.0 | all blocking gates pass; annotated local tag resolves the evidence commit |

## Explicit gaps below 10

| Gap | Severity | Impact | Corrective action | Blocks Chapter 3 | Blocks production release |
|---|---|---|---|---|---|
| Historical performance evidence was not remeasured | low | no current regression signal; terminology is now precise | rerun benchmarks when performance-sensitive source changes | no | no |
| Optional external identity provider is not integrated | low/internal | local HMAC profile remains the current trust model | integrate the selected provider when deployment requires federation | no | only if the production security plan requires federation |
| Isolated global branch coverage is 47.93% | low | low-risk read/defensive branches have less depth | add behavior tests when those paths change; do not add assertion-free coverage | no | no |
| Metrics aggregation and Redis HA are external | operational | local replicas expose correct data but do not provision production monitoring/HA | deploy Prometheus labels/dashboards and managed Redis HA | no | yes for a multi-instance production rollout |
| Root license text needs owner approval | legal/medium | package metadata alone is insufficient for public distribution | add owner-approved `LICENSE` and copyright notice | no | yes for public distribution |

No listed gap can lose required source, prevent Git reproduction, introduce a
secret, break Windows or Docker installation, break tests or migrations, leave
a critical vulnerability, or regress transaction architecture.
