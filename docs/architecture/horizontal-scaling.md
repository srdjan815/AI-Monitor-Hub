# Horizontal scaling readiness

## Correctness boundary

API and worker replicas share PostgreSQL. Correctness uses database uniqueness,
checks, row locks, optimistic version columns, job lease tokens, and attempt
fencing. It does not use in-memory locks, local sequence counters, or local
canonical caches.

```text
API replica A ----\
API replica B -----+--> PostgreSQL
worker A ----------+
worker B ----------/

API replicas ------> Redis (shared rate-limit windows, non-canonical)
Prometheus --------> each API replica separately
```

## API replicas

Requests are stateless after authentication. Request/correlation IDs and actor
context use request-local context variables. Local HMAC verification needs the
same active/previous key configuration on every replica.

The development memory limiter is process-local. Multi-replica deployments use
the Redis backend: a Lua operation uses Redis server time to atomically admit
or reject each fixed-window request. All replicas must use identical namespace,
limit, window, and capacity settings. The capacity is the number of active
`(policy, identity)` windows, not the number of unique users.

Redis holds opaque counters and expiry metadata only. An unavailable or
restarted Redis can reject protected mutations, allow configured fail-open
reads, or reset budgets; it cannot corrupt or recover domain data.

Prometheus registries remain process-local. Scrape every API target and retain
the collector-provided `instance` label. Aggregate counters with `sum`/`rate`
across instances and histograms by summing bucket rates by `le` and the desired
business labels before applying `histogram_quantile`. Never treat one replica's
counter as a service-wide total.

The repository verification topology is started explicitly:

```powershell
docker compose -f docker-compose.yml -f docker-compose.multi-instance.yml up --build api-replica-a api-replica-b
```

Only ports 18001 and 18002 belong to this proof. The explicit service list
avoids starting the separate single-instance development API on port 8000.

## Worker replicas

Claims use `FOR UPDATE SKIP LOCKED`, a random lease token, worker ID, attempt
number, and expiration. Heartbeat and finalization re-check the full lease.
Stale recovery can therefore safely make an abandoned job claimable without
letting its former worker finalize.

Delivery remains at least once. External side effects must use
`context.side_effect_key(operation)` or an equivalent downstream idempotency
contract.

## Restart behavior

- An API restart loses that replica's process-local metrics and memory-limiter
  state. Redis-backed windows remain shared while Redis remains available.
- A Redis restart is treated as resetting non-canonical rate-limit budgets.
  Redis clients reconnect; verify the configured fail policy and shared budget
  after recovery.
- An interrupted worker leaves a running lease; expiry and stale recovery
  transition it to retry/dead-letter handling.
- No local temporary artifact is required to recover a job.
- Rolling deployments must keep token keys and migration compatibility across
  the overlap window.

## Proof status

Database-level claim and fencing races have dedicated PostgreSQL tests.
Two-replica shared-limit, per-replica scrape, Redis restart, two-worker, and
rolling-restart exercises remain executable deployment gates; they cannot be
inferred from unit tests. Their exact runbook is in
`docs/operations/recovery-procedures.md`.
