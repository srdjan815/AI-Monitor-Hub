# Product Content Platform Implementation Report

Date: 2026-07-24
Branch: `feature/product-core`

## Initial state

Sprint 1 and 1.1 were present as valid uncommitted work. The pre-change suite
passed 46 tests with one pre-existing Starlette/httpx warning.

## Architecture and files

Added the isolated `app.modules.product_content` module:

- `models.py`
- `schemas.py`
- `repository.py`
- `service.py`
- `router.py`

The application router and Alembic metadata discovery were extended. Catalog
Product is referenced, not duplicated.

## Migrations

Revision `f7a8b9c0d1e2`, parent `e6f7a8b9c0d1`. Previous revisions were not
modified. Added normalized language, type, content, SEO, landing-page,
document-reference, video-reference, and change-event tables with foreign keys,
uniqueness, workflow/search indexes, revision identities, and delta cursor.

Sprint 2.1 adds `a8b9c0d1e2f3` and `b9c0d1e2f3a4`. They add scheduling and
broken-link metadata, normalized library/revision/reference tables, templates
and ordered items, normalized conditions, scoring policies/history, and
Content Type prompt versions. No earlier Alembic revision was modified.

## API and browser

APIs cover languages, content types, Product content creation/revision,
workflow, history, rollback, search, SEO, landing pages, documents, videos,
score, export, seed, and delta. The autonomous admin is at
`/api/v1/content/admin`.

Sprint 2.1 completes lifecycle APIs, reusable Blocks/Snippets/Sections,
templates and Product assignments, Product/Attribute variables, conditions,
preview, usage, configurable scoring/history, prompt history/activation,
revision diff, broken-link metadata, and cross-surface search.

## Validation and tests

Product Content tests cover idempotent language/type seed, revisions, workflow,
invalid transitions, rollback, search, SEO limits, landing/doc/video references,
score, export, delta ordering, duplicate hash metadata, AI metadata storage, and
admin loading. Final whole-repository validation is reported in the completion
response.

Completion tests cover lifecycle conflicts, library history, template
assignment and cloning, variables, conditions, preview, usage, link metadata,
scoring/history, prompts, search, and revision diff.

## Remaining limitations

References deliberately do not process media or perform URL checks. Scheduling
is metadata only. Duplicate detection remains hashing only. Browser
administration is a lightweight navigation shell and remains unauthenticated.

## Recommended Chapter 3

Chapter 2 can be closed as a stable platform boundary. Future Supplier, Import,
AI-generation, and Publishing modules should consume these normalized APIs
instead of creating alternate content storage.

## Sprint 2.2 quality audit

The initial audit found a 1,401-line router containing SQL, serialization,
revision decisions, scoring, usage, and HTML; mixed query/transaction/rendering
responsibilities in `completion.py`; repeated revision/usage patterns; an N+1
condition query; scattered protocol literals; and unsafe unescaped preview
interpolation.

The router is now a small aggregator over focused transport-only routers.
Database access is isolated in repositories, transactions and validation are
service-owned, and compatibility façade names remain available. Preview
conditions are batch-loaded and Content Score counts use a single aggregate
query. Constants are centralized by protocol responsibility.

Security controls now preserve stored source while sanitizing normal preview,
HTML-escape variable values, require explicit trusted Raw rendering, report
unknown/malformed variables, reject invalid enums at schema validation, cap
condition count, fail closed on invalid typed comparisons, and exclude dynamic
execution or traversal.

Corrective migration `c0d1e2f3a4b5` replaces the SEO historical-row-hostile
unique constraint with a partial current-row index and adds library-current
uniqueness, nonnegative ordering/weight checks, score range checks, and
usage/history/prompt indexes. Previous revisions were not changed.

Focused behavior and boundary tests cover lifecycle, revisions and rollback,
references, library/template usage and ordering, AND/OR/NOT conditions,
malformed/malicious variables, Product and Product Attribute resolution,
sanitized/trusted preview modes, scoring/history, prompt activation, schedule
validation, pagination, transaction rollback, duplicate slugs, soft deletion,
and prohibited architectural dependencies.

Sprint 2.3 added server-side raw-preview gating, Bleach sanitization, atomic
revision/workflow transactions, row locking, deterministic pagination,
condition-preserving template clones, active/current-only exports, explicit
stored-source export metadata, timezone-aware schedule validation, and
PostgreSQL invariant indexes in corrective revision `d1e2f3a4b5c6`.

The disposable PostgreSQL suite validates an empty `base -> head`, repeated
upgrade, safe `head -> c0d1e2f3a4b5 -> head`, catalog constraints, concurrent
SEO revisions, concurrent prompt creation, and injected rollback failures.
The complete repository suite currently contains 92 passing tests. The stricter
final closure audit remains NO-GO until the remainder of the requested
concurrency and failure-injection matrix is automated.
