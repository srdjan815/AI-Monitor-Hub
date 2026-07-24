# Architecture exception registry

The active registry is `ARCHITECTURE_EXCEPTIONS` in
`backend/tests/test_module_boundaries.py`. It is currently empty.

An exception entry must contain the exact path or rule identifier and a
non-empty reason. The same change must add an architecture decision record that
states owner, scope, expiry/review date, risk, and removal condition. Tests must
continue to enforce every non-exempt case.

Exceptions may not authorize repository commits, unauthenticated mutation,
duplicate Product models, stale worker finalization, invalid stock, or an
unbounded ordinary API response.
