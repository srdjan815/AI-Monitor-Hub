# Product Content Final Closure Audit

## Verdict

**NO-GO for permanent Chapter 2 closure.** No known critical or high-severity
runtime defect remains in the exercised paths, but the required concurrency
and failure-injection matrix is not yet complete. Passing tests must not be
used as a substitute for that missing evidence.

## Independent findings and corrections

The audit confirmed that trusted raw preview relied on a client boolean; the
custom HTML parser was not a sufficient sanitizer; workflow revisions could
commit before their metadata/events; template clones omitted normalized
conditions; exports mixed historical/inactive data with current data and did
not label raw source; several lists lacked deterministic secondary ordering;
and current-revision/active-prompt uniqueness was not a final database
boundary. Naive schedule datetimes were also accepted.

The implementation now uses a disabled-by-default server setting and Bleach,
performs revision/workflow writes in one service-owned transaction, clones
conditions, filters and labels exports, applies stable ordering, rejects naive
datetimes, locks competing writers, and translates integrity conflicts. New
revision `d1e2f3a4b5c6` adds partial unique indexes and scheduling checks without
changing an older migration.

Suspected findings that were not defects: HTTP tests already use PostgreSQL;
flat condition rows cannot form cycles; no dynamic `eval`/`exec` path exists;
and a heterogeneous export is not by itself proof of an N+1 query.

Supplier, Import, Pricing, Inventory, AI execution, Scraper, Media Processing,
Publishing, and a complete authorization platform remain outside Chapter 2.

## Dependency and transaction diagram

```text
FastAPI router -> focused service class -> repository -> PostgreSQL
                         |                    |
                         | commit/rollback    +-- query/add/flush only
                         +-- validation, locks, domain errors

Catalog Product/Product Attributes -> Product Content variable resolution
Product Content -> no Supplier/Import/Pricing/Inventory execution dependency
```

Current Product Content, SEO, and Landing revisions have partial unique
indexes. Prompt activation has one active-version index per Content Type.
History is retained; active exports omit deactivated/historical reusable
objects.

## Verified results

- Full pytest: 92 passed, 0 failed, 0 skipped.
- PostgreSQL: disposable empty `base -> head`, repeated upgrade, and safe
  `head -> c0d1e2f3a4b5 -> head` passed.
- Alembic: one head `d1e2f3a4b5c6`; current equals head; no model drift.
- Concurrency: independent-session SEO revision conflict and prompt version
  serialization passed; database uniqueness remained the final boundary.
- Failure injection: revision/event and template-clone failures left no partial
  state.
- OpenAPI: normalized structural snapshot covers Product Content paths and
  selected schemas; runtime has 152 paths, 223 operations, and no duplicate
  operation IDs.
- Security: script/SVG/MathML/URL/event/srcdoc/data/CSS/malformed/template
  traversal payloads are covered; public/default raw preview returns 403.
- Time: offset-aware inputs and invalid/equal schedule ranges are covered by
  schema/database validation.
- Query counts: representative 20-block preview is bounded to 6 queries and
  scoring to 2.
- Ruff, Ruff C901, compilation, mapper configuration (46 tables), `pip check`,
  Compose validation, `/health`, `/docs`, OpenAPI, PostgreSQL, and Redis passed.

## Service organization decision

`services.py` is physically large, but contains focused public service classes
with explicit transaction boundaries and small methods. Splitting it during a
failure audit would primarily relocate shared imports/base behavior and expand
compatibility/circular-import surface. The file is retained as intentional
organizational debt; a later mechanical split must preserve exports from
`service.py` and introduce no service-to-service coupling.

## API and content safety contract

Stored source remains unchanged. Normal preview returns sanitized output.
Trusted raw preview is disabled by default and must later be protected by
authorization in addition to configuration. Export responses declare
`representation=stored_source`, `sanitized=false`, and `publishable=false`.
Publishing must never consume stored source directly.

## Remaining closure blockers and limitations

The audit still lacks dedicated independent-session tests for simultaneous
Landing revisions, Product Content revisions, rollback operations, template
reordering, library assignment versus deactivation, score-history writes, and
several requested mid-transaction failure points. It also lacks a preserved
pre-refactor OpenAPI artifact; the new structural snapshot is a forward
regression boundary, not proof of every historical nullable/error-response
detail. Performance measurements cover preview and scoring, not the complete
100-product workflow matrix. Dependency ranges remain broader than a lockfile;
Ruff is pinned, and `pip check` is clean, but an advisory scanner was not
available. Optional MyPy validation reports 47 errors across seven files,
dominated by existing generic service return types, SQLAlchemy result typing,
and the missing third-party Bleach stub.

Future Supplier/Import consumers may reference canonical Product Content
identifiers and public service/API contracts only. They must not write revision
tables directly or bypass Product Content transaction and output-safety rules.

Permanent closure requires completing the missing concurrency, failure, full
query-count, and historical-contract evidence, then rerunning this gate.
