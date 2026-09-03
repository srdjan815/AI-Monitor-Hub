# Cursor and response pagination

## Compatibility contract

Existing offset parameters remain available. High-volume endpoints add:

```text
pagination=cursor
cursor=<signed opaque token>
limit=<bounded integer>
```

Supplying a cursor implicitly selects cursor mode. Cursor mode rejects a
non-zero offset and rejects `pagination=offset`. Existing response bodies keep
their shape; continuation metadata is returned through `X-Next-Cursor` and
snapshot headers.

## Time/UUID cursor

Rows use an immutable timestamp and UUID tie-breaker:

```text
(created_at DESC, id DESC)
```

An ascending history may use:

```text
(occurred_at ASC, id ASC)
```

The first page obtains PostgreSQL `now()` and restricts rows to
`created_at <= snapshot_at`. The cursor carries the last timestamp, last UUID,
and snapshot timestamp. Queries load `limit + 1`; no count is required merely
to determine continuation.

## Revision cursor

Revision histories use:

```text
(revision DESC, id DESC)
```

The snapshot is the maximum revision observed on the first page. Subsequent
pages require `revision < last_revision` and
`revision <= snapshot_revision`. Prompt history uses its equivalent `version`
column.

## Integrity

Cursors are URL-safe JSON plus HMAC-SHA256. They include:

- format version;
- resource identifier;
- SHA-256 digest of normalized filters, ordering, and limit;
- complete keyset position;
- snapshot boundary.

Changing a filter, limit, resource, or ordering invalidates the cursor.
Tampering, malformed Base64, naïve timestamps, and wrong tuple shapes return
HTTP 400 with stable code `INVALID_CURSOR`.

## Currently covered high-volume paths

- Products;
- warehouses, balances, movements, reservations;
- execution jobs;
- Product Attribute values, resolved layouts, and history;
- Product Content entries, references, SEO, landing pages, library, score
  history, and revision histories.

Reference/admin lists remain offset-paginated but have hard maximum limits.
Complete resolved-attribute export is a streaming NDJSON endpoint and does not
reuse the ordinary response.

## Index rule

Every keyset query must end with the unique UUID tie-breaker, and an index must
match its filters and direction before an index migration is justified.
Indexes are added only after `EXPLAIN (ANALYZE, BUFFERS)` demonstrates the need.
Changing an ordering column is an API contract change because it changes cursor
semantics.
