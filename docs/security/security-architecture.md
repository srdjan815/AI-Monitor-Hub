# Security architecture

## Trust boundary

Every route except root/health authenticates through the router-level
`authorize_request` dependency. Authorization is permission-based and separate
from domain services. Services receive actor identity from request context, not
from an untrusted payload.

`AuthenticationAdapter` isolates token verification. The local implementation
uses fixed HS256, a three-segment JWT-like token, key ID, issuer, audience,
version, issue/activation/expiry times, roles, actor type, and optional JTI.
Untrusted headers cannot select another algorithm.

## Key lifecycle

Only `AUTH_KEY_ID`/`AUTH_SECRET` signs new tokens. `AUTH_PREVIOUS_KEYS` verifies
unexpired tokens during rotation and cannot shadow the active key. Production
requires a strong non-default secret, bounded TTL/skew, explicit issuer and
audience, and rate limiting.

Legacy two-segment verification is an explicit temporary compatibility switch.
There is no distributed JTI deny-list; short token lifetime and key retirement
are the current revocation controls. Public/federated deployment should replace
the adapter with OIDC or add shared revocation.

## Authorization

Catalog, Attributes, Content, Inventory, and Execution use separate read,
write, approval/adjustment, and administrative permissions. Seed, raw preview,
prompt/scoring administration, execution lifecycle, and metrics are privileged.
Trusted raw preview additionally requires a disabled-by-default deployment
feature flag.

Missing/invalid credentials return 401. A valid principal without permission
returns 403. Authentication failures do not disclose signature, key, subject,
or claim-validation details.

## Boundary defenses

- Transport request size is checked before body parsing.
- Pydantic/domain constraints bound high-risk content, prompt, JSON, and list
  payloads.
- Signed cursors reject tampering and filter reuse.
- High-risk seed, preview, bulk, search, export, and execution paths use stable
  429 responses and `Retry-After`.
- CORS/trusted-host behavior is deployment-configured.
- Formula parsing uses the restricted formula engine, not Python evaluation.
- Normal preview sanitizes stored source.

The rate limiter has two backends. The memory backend is process-local for
development and single-instance use. The Redis backend executes one atomic
fixed-window Lua decision against Redis server time and shares the result
across API replicas. Redis holds only bounded opaque `(policy, identity)`
counters and expiry metadata; it is not an authorization source or canonical
domain store.

A valid Bearer credential is verified before selecting its actor identity.
Invalid, missing, non-ASCII, or duplicate credentials use the peer identity.
Forwarded addresses are accepted only from configured proxy networks and are
walked right to left. Uvicorn proxy-header rewriting stays disabled so there is
one client-address trust decision.

Rate limiting does not replace authentication, permission checks, request
boundaries, transaction isolation, or gateway controls. Shared Redis failures
follow an explicit policy: protected reads may fail open, protected mutations
fail closed in production, and no Redis condition changes canonical
PostgreSQL correctness. Redis restart resets are acceptable only because the
budgets are non-canonical.

## Logging and metrics

Structured logs contain request/correlation/actor/route/status/duration but not
authorization headers, tokens, signing material, raw prompts, content, or full
payloads. Metrics labels use route templates or finite early-rejection policy
labels, never concrete entity IDs. Prometheus metrics remain process-local even
when rate-limit decisions are shared; every API replica must be scraped with a
distinct target `instance` label and aggregated by the collector.

See `api-authorization-matrix.md`, `token-lifecycle.md`, and
`rate-limiting.md` for the detailed contracts.
