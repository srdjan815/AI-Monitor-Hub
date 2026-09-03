# Platform Foundation

## Runtime boundaries

The application uses one canonical dependency direction:

`FastAPI router -> service/coordinator -> repository -> SQLAlchemy/PostgreSQL`

Routers parse HTTP input, apply authentication/authorization, call services, and
map responses. Repositories own SQL and flush mutations but never commit.
Services own validation and transaction commit/rollback. Architecture tests in
`backend/tests/test_module_boundaries.py` enforce these rules.

Catalog owns the canonical `Product`. Inventory and Product Content reference it
and must not redefine it. Public compatibility façades preserve the established
imports while Catalog, Inventory, Product Attributes, and Product Content are
physically split into responsibility-focused services and repositories. The
façades coordinate the same shared session and do not own SQL or transactions.

## Cross-cutting foundation

- All non-health API routes are authenticated at router inclusion.
- Central policy maps route and method to permissions.
- Request IDs are accepted or generated and returned on responses.
- A transport body ceiling precedes schema validation.
- Domain limits constrain large text and JSON fields.
- API errors expose `detail`, stable `code`, and `request_id`.
- List queries use a unique identifier as their final ordering key.
- High-volume lists offer signed, filter-bound keyset cursors; retained offsets
  are compatibility mode.
- Ordinary resolved-attribute responses are bounded and normalized. Complete
  retrieval uses the separate streaming NDJSON export.
- Mutable aggregates use version checks where concurrent lost updates matter.
- Execution workers use heartbeat leases and fenced finalization.
- Rate-limit counters and the built-in metrics registry are process-local. This
  is safe only behind a trusted/internal boundary or with enforcement and
  aggregation supplied by shared infrastructure, as documented in the scaling
  and rate-limit policies.

## Chapter 3 rule

New modules must use the same security dependency, actor propagation, service
transaction boundary, deterministic ordering, error model, and migration policy.
They may not query another module's tables from routers or duplicate Product.
The foundation is governed by
[`foundation-freeze-policy.md`](foundation-freeze-policy.md); changes to these
rules require an explicit architecture review and recorded exception.
