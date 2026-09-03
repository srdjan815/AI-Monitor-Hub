# Isolated destructive test environment

> **TEST ONLY — EPHEMERAL — NO REAL DATA — NOT FOR DEVELOPMENT**
>
> This environment is deliberately destroyed after every run. Never enter real
> supplier credentials, never attach a development or production database, and
> never continue application development inside its containers.

The isolated test system exists to run database, Redis, concurrency, supplier,
failure-injection, and random-order tests without touching the normal AI Monitor
Hub environment. It is defined by `docker-compose.test-isolated.yml` and must be
started only through `scripts/Invoke-IsolatedTestSuite.ps1`.

## Safety boundaries

- The Compose project has a unique `amh-test-<random>` name for every run.
- PostgreSQL uses only the database `amh_ephemeral_test_only`.
- PostgreSQL and Redis data directories are `tmpfs`; no application data volume
  or supplier secret file is mounted.
- The API exposes no host port.
- Authentication and supplier secrets use test-only modes.
- The runner rejects configuration containing normal database/volume names,
  host ports, or `supplier-secrets.json`.
- A `finally` block removes containers, networks and volumes on success or
  failure and verifies that cleanup completed.

There is deliberately no "keep failed environment" option. Cleanup is mandatory
after success, failure, timeout, or interruption. Diagnostics must come from the
captured test and container logs, never from retaining a data-bearing test stack.

## Commands

From the repository root in Windows PowerShell:

```powershell
.\scripts\Invoke-IsolatedTestSuite.ps1 -Suite full
.\scripts\Invoke-IsolatedTestSuite.ps1 -Suite supplier
.\scripts\Invoke-IsolatedTestSuite.ps1 -Suite random -RandomRuns 5
.\scripts\Invoke-IsolatedTestSuite.ps1 -Suite random -RandomRuns 1 -RandomSeed 2079130918
.\scripts\Invoke-IsolatedTestSuite.ps1 -Suite stress -RandomRuns 5
```

`full` runs the complete serial backend suite. `random` recreates the entire
database and Redis instance for every recorded random seed. `stress` adds a
normal pass, random-order passes and an xdist pass restricted to read-only
architecture and static-analysis tests. Database and Redis tests already create
concurrent requests inside their own test cases; they are deliberately kept in
one pytest process so independent workers cannot seed or clean the same test
database. Migration and destructive lifecycle tests are never run concurrently
with other tests. A release
decision must record the exact command, seeds, results, and verified cleanup.

## Non-negotiable rule

If a future change needs a real credential, persistent volume, host database,
host port, or development data in this Compose file, stop. That change belongs
in a different environment and requires an explicit architecture and security
review. Weakening a safety assertion to make the runner start is prohibited.
