# Security Architecture

## Authentication boundary

`app/core/security.py` exposes an `AuthenticationAdapter` protocol. The active
implementation, `LocalHMACAuthenticationAdapter`, is deliberately isolated from
route authorization so a future OIDC verifier can replace local HMAC without
rewriting routers.

New local tokens use three signed segments and a fixed header:

```json
{"alg":"HS256","kid":"<active-key-id>","typ":"JWT"}
```

The verifier never selects an algorithm from untrusted input. It requires the
configured issuer, audience and token version, validates `iat`, optional `nbf`,
`exp`, subject, actor type, roles and optional `jti`, and applies a bounded clock
skew. Unknown roles, duplicate roles, unknown key IDs, malformed claims and
oversized tokens fail with the same 401 contract.

The active secret is selected by `AUTH_KEY_ID`. `AUTH_PREVIOUS_KEYS` is a
key-ID-to-secret JSON object used only for verification during rotation. The
active key ID may not appear in that map. Two-part tokens from the earlier local
format remain verifiable while `AUTH_ALLOW_LEGACY_TOKENS=true`; they are marked
as token version zero and should not be newly issued.

## Authorization and actor propagation

A principal contains a stable subject, actor type, roles, permissions, token
version, optional JTI and verified key ID. `authorize_request` authenticates
before a protected route executes, selects the path/action permission, and
places the principal in request state plus a request-local context. Existing
audit fields therefore use the authenticated subject rather than a
client-supplied actor.

Health endpoints are public. Reads require domain read permissions; mutations
require write, approval, adjustment, submission or lifecycle permissions. Seed
is privileged. Trusted raw preview requires both `content.raw_preview` and the
disabled-by-default server feature flag. Metrics require `admin.access`.

## Boundary and residual risk

HMAC is suitable for this internal foundation only when issuance is restricted
to a trusted service and signing keys are stored outside source control. It does
not provide federated login. JTI is carried for audit/idempotency integration,
but there is no distributed revocation store; short expiry and emergency key
retirement are the current revocation controls. See
`docs/security/token-lifecycle.md`.

Rate limiting is defense in depth. The built-in backend is per process; an edge
or shared backend is required before a multi-instance deployment is exposed to
untrusted networks.
