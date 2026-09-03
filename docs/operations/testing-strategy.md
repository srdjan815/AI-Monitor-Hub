# Testing Strategy

> **TEST SYSTEM SEPARATION:** destructive integration and stress testing runs
> only through `scripts/Invoke-IsolatedTestSuite.ps1`. The environment is
> ephemeral, contains no real credentials or persistent application volumes,
> and is not a development environment. See
> [isolated-test-environment.md](isolated-test-environment.md).

The normal gate runs collected pytest tests against PostgreSQL, followed by
Ruff, C901, compilation, mapper configuration, Alembic check, clean MyPy,
`pip check`, OpenAPI snapshots, architecture boundaries, and `git diff --check`.

Critical concurrency tests use independent sessions and real PostgreSQL. The
Execution suite races idempotent submission and proves a stale worker cannot
finalize a recovered job. Before the final source decomposition, its focused
PostgreSQL concurrency group passed five consecutive repetitions and the focused
worker group passed 35 tests. These are prior-turn observations, not substitutes
for a fresh final gate after all edits.

Security tests cover public/protected classification, 401/403 behavior,
privileged route families, invalid/expired tokens, raw-preview double gating,
request 413 behavior, request correlation, and production settings.

Every release reruns the full serial suite, five deterministic random seeds,
xdist, branch coverage, architecture/authorization/OpenAPI groups,
cross-domain concurrency, failure injection, restart/recovery, and
multi-instance rate-limit integration. Prior evidence never substitutes for
the current commit's result. The release procedure and final audit report
record exact commands and counts.

Status-code-only assertions are insufficient for new tests: assert database
state, invariants, actor identity, error code, history/event effects, and
rollback. Mandatory regressions may not be hidden by skips, xfails, or an
unreviewed baseline.
