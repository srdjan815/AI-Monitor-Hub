# Rate Limiting

`RateLimitMiddleware` applies a fixed-window policy to high-risk paths:

| Policy | Covered requests |
|---|---|
| `seed` | attribute and Product Content seed mutations |
| `preview` | expensive content preview mutations |
| `execution` / `execution-control` | job submissions and lifecycle mutations |
| `bulk` | bulk writes, recalculation, import, reorder, expiry, and mutation validation |
| `validation` | dependency-validation reads |
| `export` | export reads |
| `search` | registered search paths and requests with a `search` query parameter |
| `query` | malformed or excessive query-field input assigned to a bounded policy |

Limits are configured by `RATE_LIMIT_REQUESTS` and
`RATE_LIMIT_WINDOW_SECONDS`. Rejections use HTTP 429, stable code
`RATE_LIMITED`, `Retry-After`, `Cache-Control: no-store`, and the request ID.
Ordinary routes do not consume a high-risk budget.

## Backends and window semantics

`RATE_LIMIT_BACKEND=memory` selects a thread-safe, process-local backend. It
uses monotonic process time and is appropriate for development, tests, or one
internal API process. Each API replica has an independent budget and an API
restart clears that replica's windows.

`RATE_LIMIT_BACKEND=redis` selects the shared backend. One atomic Lua operation
uses Redis server time, removes expired registry entries, checks capacity,
increments the fixed-window counter, assigns its TTL, and returns the remaining
TTL used for `Retry-After`. All replicas using the same Redis database,
`RATE_LIMIT_NAMESPACE`, request limit, and window therefore share one budget.
The namespace uses one Redis Cluster hash tag so the registry and counters are
in the same slot.

Redis receives only keyed-HMAC-derived, backend-hashed identifiers, counts, and
expiry scores. It never stores a token, actor name, client address, request
payload, or canonical domain state. The Redis client pool is bounded by
`RATE_LIMIT_REDIS_MAX_CONNECTIONS`.

`RATE_LIMIT_MAX_CLIENTS` bounds active `(policy, identity)` windows, not unique
people. One actor using three policies occupies three active entries. Expired
entries are pruned before admitting a new identity. At capacity, a new entry is
rejected with 429; an existing active entry is never evicted or reset to make
room.

## Identity and proxy trust

The limiter verifies a single Bearer credential and keys a valid credential by
authenticated actor subject. Separately issued tokens for the same actor share
the same policy budget. A missing, invalid, non-ASCII, or duplicate
Authorization header falls back to the network peer identity instead of
creating a credential-controlled key.

The direct peer address is authoritative unless it belongs to
`RATE_LIMIT_TRUSTED_PROXY_CIDRS`. For a trusted peer, exactly one valid
`X-Forwarded-For` chain is parsed from right to left; trusted proxy hops are
removed and the first untrusted address becomes the client identity. Invalid or
duplicate forwarded headers fall back to the direct peer.

Compose starts Uvicorn with `--no-proxy-headers`. Keep that setting: Uvicorn
must not rewrite `scope.client` before the application applies its own trusted
proxy policy. The ingress must overwrite, not append to an untrusted inbound
forwarded header, must block direct API-container access, and its addresses
must match `RATE_LIMIT_TRUSTED_PROXY_CIDRS`.

## Backend failure and restart

Redis timeout or connection errors never affect PostgreSQL transactions or
canonical reads. The default unavailable-backend policy is:

- reads fail open and continue to the application;
- mutations fail closed with HTTP 503,
  `RATE_LIMIT_BACKEND_UNAVAILABLE`, `Retry-After: 1`, and no domain mutation.

`RATE_LIMIT_FAIL_OPEN_READS` and `RATE_LIMIT_FAIL_OPEN_MUTATIONS` make those
choices explicit. Production validation forbids fail-open mutations. A Redis
restart is treated as a reset of the non-canonical rate-limit windows. A brief
post-restart burst is therefore possible; no Catalog, Inventory, Content, or
Execution state may be reconstructed from or blocked on recovery of those
counters.

Backend failures, fail decisions, and identity-capacity rejections are exposed
through `amh_rate_limit_backend_failures_total`. Ordinary limit rejections use
`amh_rate_limit_rejections_total`.

`RATE_LIMIT_ENABLED` defaults off for development/test convenience.
`RATE_LIMIT_SHARED_REQUIRED=true` requires both an enabled limiter and the
Redis backend. `APP_ENV=production` additionally requires shared Redis limiting
and fail-closed mutation behavior.

## Two-replica verification mode

Start only the two protected replicas and their dependencies:

```powershell
docker compose -f docker-compose.yml -f docker-compose.multi-instance.yml up --build api-replica-a api-replica-b
```

Replica A listens on `http://localhost:18001` and replica B on
`http://localhost:18002`. Do not use an unqualified `up` as the verification
command: the base Compose file also defines the single-instance development
API on port 8000. Send one actor's high-risk requests alternately to ports
18001 and 18002 and verify that both consume the same Redis window.
