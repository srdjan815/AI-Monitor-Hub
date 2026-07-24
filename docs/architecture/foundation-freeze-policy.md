# Foundation freeze policy

## Frozen surface

After a GO decision, the following are frozen:

- canonical module direction and Product ownership;
- router/service/repository transaction boundaries;
- public route paths, methods, operation IDs, request and response schemas;
- stable error codes and authentication dependency;
- migration history and one-head policy;
- Inventory invariants and Execution lease/fencing semantics;
- signed cursor format version and ordering contracts;
- Product Content revision semantics.

Compatibility façades may remain. Removing one requires a repository-wide usage
proof and an approved compatibility change.

## Changes requiring architecture review

Review is mandatory for:

- a new cross-module database dependency;
- another owner of Product or product identity;
- a repository commit or router SQL/session access;
- a new table, migration branch, destructive migration, or old-revision edit;
- a breaking route/schema/operation-ID change;
- mutable canonical caching;
- a new worker state or delivery-semantics claim;
- process-local state that affects correctness;
- a high-volume endpoint without a bounded/keyset/streaming contract;
- relaxing authentication, authorization, request limits, raw-preview gates,
  or optimistic locking.

## Migration policy

Old Alembic revisions are immutable. Every schema correction is a new revision
with one down-revision and a reversible downgrade where data safety permits.
The gate is empty-to-head, populated upgrade, current=head, drift check, and
downgrade/re-upgrade for new revisions.

## API compatibility

Prefer additive parameters, endpoints, and headers. Offset pagination remains
until an approved deprecation. Cursors are opaque. Errors retain stable code
and request ID. A security-required breaking change must be explicitly
classified and documented.

## Performance and security regressions

A change is rejected if it:

- reintroduces an ordinary unbounded collection or multi-megabyte accidental
  response;
- removes a unique cursor tie-breaker;
- exceeds a documented p95 budget by more than the allowed tolerance without
  measured justification;
- permits lost updates, invalid stock, stale job finalization, or duplicate
  non-idempotent effects;
- weakens token verification, route permissions, request limits, or logging
  redaction.

## New module integration

Chapter 3 modules import canonical IDs and public services, not another
module's repository internals. New modules receive their own model, schema,
repository, service, router, migration, authorization policy, bounded lists,
transaction tests, concurrency tests, and architecture dependency test.

Inventory remains optional downstream. Supplier, Import, Matching, Pricing,
AI, Media, Publishing, and ERP Sync may not use Inventory as a prerequisite
without a new architecture decision.

## Exceptions

Rare exceptions are declared in the relevant architecture test's
`ARCHITECTURE_EXCEPTIONS` map with a non-empty reason and a linked decision
record. A skip, xfail, blanket ignore, empty reason, or undocumented allowlist
entry is not an exception mechanism.
