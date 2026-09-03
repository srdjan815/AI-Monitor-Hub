# Release procedure

## Purpose

This procedure creates a reviewable Foundation release from Git alone. It does
not authorize a remote push, production migration, or deployment.

## 1. Establish recovery and identity

Before editing or staging:

1. Record branch, status, migration head, image IDs, OpenAPI hash, and lock hash.
2. Create and verify a checkpoint outside the repository.
3. Hash all Git-visible source, migrations, tests, scripts, configuration, and
   documentation.
4. Confirm that `.env`, virtual environments, caches, coverage, local databases,
   and temporary archives are excluded.

Do not continue without a readable checkpoint.

## 2. Review every path

Generate `docs/audits/final-git-file-classification.csv` from the union of
tracked and untracked paths. Assign exactly one approved classification, owner,
reference evidence, secret result, duplicate result, inclusion decision, and
commit group to every row.

Resolve uncertain, sensitive, temporary, and obsolete paths before staging.
Never delete a file solely because it is untracked.

Run deterministic secret searches over tracked modifications and untracked
files, then repeat over the exact staged content. Verify `.env` is ignored
without copying its contents into a report.

## 3. Run the pre-commit gates

The required gate set is defined by the release sprint and includes:

- compilation, imports, mapper configuration;
- Ruff, Ruff formatting, C901, and clean MyPy;
- host and Docker `pip check`;
- host and Docker dependency advisory scans;
- serial, randomized, xdist, branch-coverage, architecture, authorization,
  concurrency, and failure-injection tests;
- empty-to-head, populated upgrade, downgrade/re-upgrade, and Alembic drift;
- clean no-cache image build and Compose restart/recovery checks;
- OpenAPI regeneration and deterministic contract hashes;
- secret scans and `git diff --check`.

Record exact commands, timestamps, versions, counts, and outcomes. A result from
before the final source, dependency, or configuration edit is not final
evidence.

## 4. Stage explicitly

Stage reviewed logical groups with explicit paths; do not use an unreviewed
`git add .`.

For each group:

```powershell
git diff --cached --name-status
git diff --cached --check
git diff --cached
```

Then rerun the staged secret scan, source-import validation, and migration graph.
Every staged path must have an approved row in the classification CSV.

Use fewer, larger commits when splitting would create an invalid intermediate
repository. Each commit should remain internally consistent where practical.

## 5. Commit and record

Create professional, scope-based commit messages without fabricating authorship.
After each commit record:

- commit hash and message;
- exact file inventory;
- gates supporting that commit;
- migration head and lock hash.

Do not amend unrelated history and do not push.

## 6. Reproduce from committed Git state

Create a fresh clone in a disposable directory. Do not copy untracked source:

```powershell
$ReleaseClone = Join-Path $env:TEMP ("ai-monitor-hub-release-" + [guid]::NewGuid())
git clone --no-local . $ReleaseClone
Set-Location $ReleaseClone
Copy-Item .env.example .env
docker compose -p amh-release-check config --quiet
docker compose -p amh-release-check build --no-cache
docker compose -p amh-release-check up -d
docker compose -p amh-release-check ps
```

Use the isolated Compose project to create a new database volume, migrate empty
to head, start API/workers, and run the full gate set. Compare the original and
clone:

- committed source hashes;
- migration head and mapped-table count;
- exact requirements hash and installed application versions;
- OpenAPI counts and normalized hash;
- collected/passed test counts;
- image IDs.

Any unexplained mismatch blocks the release. Preserve evidence before removing
the disposable environment.

## 7. Create the local Foundation tag

Only after final validation and a clean or explicitly documented status:

```powershell
git tag -a foundation-v1.0 -m "Foundation v1.0: Product Core, Product Attributes, Product Content, Inventory, Execution, migrations, security, performance, and tests"
git rev-parse HEAD
git rev-parse "foundation-v1.0^{commit}"
```

The two hashes must match. Record the tag in the final report. Do not push the
tag without separate authorization.

## 8. Final report and handoff

Create `docs/audits/post-freeze-repository-release-final-report.md` with the
complete evidence and scorecard. Report remaining external infrastructure
requirements separately from local failures.

The recommended next branch point is:

```text
feature/supplier-platform
```

Do not begin that module as part of release closure.
