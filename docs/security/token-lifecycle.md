# Token Lifecycle

## Issuance

Only the configured active key signs new tokens. Required claims are `sub`,
`roles`, `type`, `iat`, `exp`, `iss`, `aud` and `ver`; `jti` is emitted by
default and `nbf` is optional. Default lifetime is
`AUTH_TOKEN_TTL_SECONDS`. Clock tolerance is bounded by
`AUTH_CLOCK_SKEW_SECONDS` (maximum five minutes).

Applications must not log tokens, signatures or signing secrets. JTI is an
identifier, not a secret.

## Verification

The verifier:

1. bounds token length and requires exactly two legacy segments or three current
   segments;
2. requires `alg=HS256`, `typ=JWT`, and a known `kid` for current tokens;
3. verifies HMAC before trusting claims;
4. validates issuer, audience and token version;
5. validates activation and expiration with configured skew;
6. rejects unknown or duplicate roles and malformed identity claims.

All failures return 401 `AUTHENTICATION_REQUIRED` without revealing which check
failed.

## Rotation

1. Generate a new random secret of at least 32 characters and a new key ID.
2. Move the old active key into `AUTH_PREVIOUS_KEYS`.
3. deploy the new `AUTH_SECRET` and `AUTH_KEY_ID`; new tokens immediately use
   the new key while unexpired old tokens remain valid;
4. wait at least the maximum token lifetime plus clock skew;
5. remove the old key from `AUTH_PREVIOUS_KEYS`.

The active key ID is rejected if duplicated in the previous-key map. A removed
key immediately invalidates every token signed by it.

## Legacy and revocation policy

Two-part legacy tokens are accepted only when
`AUTH_ALLOW_LEGACY_TOKENS=true`. Disable that setting after the longest legacy
token lifetime has elapsed.

There is no distributed JTI deny-list in this repository. Normal revocation is
therefore short-lived expiry; emergency revocation removes or rotates the
signing key. External/public deployment should replace the adapter with OIDC or
add a shared revocation service.
