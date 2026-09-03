# Production Configuration

Set `APP_ENV=production`, a non-default database URL, an unpredictable
`AUTH_SECRET` of at least 32 characters, explicit CORS origins, explicit allowed
hosts, `RATE_LIMIT_ENABLED=true`, `RATE_LIMIT_BACKEND=redis`,
`RATE_LIMIT_SHARED_REQUIRED=true`, `RATE_LIMIT_FAIL_OPEN_MUTATIONS=false`, and
`DOCS_ENABLED=false`. Production validation rejects wildcard or missing
origins, wildcard hosts, weak/default secrets, known default database
passwords, a non-shared limiter, fail-open mutations, trusted raw preview, and
enabled interactive docs.

Set a stable `AUTH_KEY_ID`, issuer, audience and token version. During rotation,
put old verification-only secrets in the JSON `AUTH_PREVIOUS_KEYS` map. The
active key ID cannot also be a previous key ID.

`BACKEND_CORS_ORIGINS` is normalized deterministically. Credentials are disabled
by default and can never be combined with wildcard origins. Compose does not use
Uvicorn reload.

`MAX_REQUEST_BODY_BYTES` defaults to 2 MiB and may not be below 64 KiB. Oversized
transport requests return 413 without truncation. Schema violations return 422.
Large future imports and media must use a dedicated streaming/object-storage
path, never ordinary JSON endpoints.

The deployment terminator must enforce an equal or lower body limit, sanitize
forwarded headers, and restrict direct container access.

## Shared rate limiting

Production API replicas must share the same `REDIS_URL`, `REDIS_DB`,
`RATE_LIMIT_NAMESPACE`, `RATE_LIMIT_REQUESTS`,
`RATE_LIMIT_WINDOW_SECONDS`, and `RATE_LIMIT_MAX_CLIENTS`. Redis is operational
protection, not a canonical database: an outage follows the configured
read/mutation fail policy and never changes PostgreSQL correctness.

The default and approved production policy lets protected reads continue when
Redis is unavailable and rejects protected mutations with HTTP 503 before they
reach domain logic. Set `RATE_LIMIT_FAIL_OPEN_READS=false` when availability
policy requires protected reads to fail closed as well. Production never
permits `RATE_LIMIT_FAIL_OPEN_MUTATIONS=true`.

`RATE_LIMIT_MAX_CLIENTS` bounds active `(policy, identity)` windows. Size it for
the number of simultaneously active policy identities, not merely the number
of users. Treat a Redis restart as a reset of these non-canonical budgets and
retain gateway protection for the possible post-restart burst.

## Proxy boundary

The provided Compose command disables Uvicorn proxy-header rewriting with
`--no-proxy-headers`. Preserve this in derived deployments. Configure only the
actual ingress addresses in `RATE_LIMIT_TRUSTED_PROXY_CIDRS`, make the ingress
overwrite inbound `X-Forwarded-For`, and prevent clients from reaching API
replicas directly. The application validates one forwarded chain and walks it
right to left; invalid or duplicate headers fall back to the direct peer.

Do not enable Uvicorn's independent `FORWARDED_ALLOW_IPS` processing alongside
the application policy. Two independent trust configurations can disagree
about which address is the client.

## Multi-replica launch contract

The repository's verification overlay is started with the explicit service
list:

```powershell
docker compose -f docker-compose.yml -f docker-compose.multi-instance.yml up --build api-replica-a api-replica-b
```

The replicas listen on ports 18001 and 18002 and depend on healthy PostgreSQL
and Redis services. The base API deliberately remains suitable for
single-instance development and is not part of this command.
