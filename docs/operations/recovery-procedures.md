# Recovery procedures

## Principles

Recover in an isolated environment first. Preserve the database and logs before
changing state. Do not edit an applied Alembic revision, manually clear a job
lease, or delete history to make a health check pass.

## Database restore

1. Record application version, Alembic current/head, database version, and the
   incident timestamp.
2. Stop mutating traffic and workers through deployment controls.
3. Take a final database backup if storage is readable.
4. Restore the selected backup into a separate PostgreSQL instance.
5. Run:

   ```powershell
   docker compose exec -T api alembic current
   docker compose exec -T api alembic heads
   docker compose exec -T api alembic check
   ```

6. Upgrade the isolated restore to the application head if required.
7. Run mapper configuration, invariant queries, and representative read-only
   API checks.
8. Switch traffic only after Product, stock, revision-current, and job-state
   invariants pass.

Never reconstruct a missing revision by guessing from ORM metadata when the
live schema or a reachable Git object can provide evidence.

## Failed migration deployment

If a new revision fails before commit, correct it with a new revision when any
environment may have applied it. Downgrade only when the revision's downgrade
is proven data-safe and the owner approves. Verify one head, current=head,
empty-to-head, populated upgrade, and downgrade/re-upgrade in isolation.

## Worker interruption and stale leases

Do not manually mark a running job successful. A stopped worker's lease expires;
stale recovery moves the job into bounded retry/dead-letter handling. Inspect
job attempts and correlation ID, then:

- leave retryable work to automatic backoff;
- use manual retry only from `FAILED` or `DEAD_LETTER`;
- cancel only through the lifecycle API;
- verify any external side effect with its stable side-effect idempotency key.

A lease-token mismatch means the old worker lost ownership; its result must be
discarded.

## API or worker rolling restart

1. Verify database current=head and backward compatibility across the overlap.
2. Keep active and previous auth keys identical on all API replicas.
3. Start one new API replica and run health, OpenAPI, authenticated read, and
   401/403 checks.
4. Drain one old API replica at a time.
5. Start new workers before stopping old workers; expect leases owned by
   stopped workers to expire and recover.
6. Verify claim, heartbeat, retry, cancellation, and queue-depth metrics.

## Redis outage

Redis is not canonical for any current domain. It may hold shared rate-limit
windows, but API/database correctness remains in PostgreSQL.

For a Redis outage or restart:

1. Keep PostgreSQL and API evidence intact; do not modify domain rows or
   migrations to address a limiter incident.
2. Confirm both API replicas report backend failures through
   `amh_rate_limit_backend_failures_total`, separated by `instance`, `policy`,
   and `decision`.
3. Expect protected reads to follow `RATE_LIMIT_FAIL_OPEN_READS`. Production
   protected mutations fail closed with HTTP 503,
   `RATE_LIMIT_BACKEND_UNAVAILABLE`, and `Retry-After: 1` before domain logic.
4. Do not switch replicas independently to the memory backend. That creates
   fragmented budgets and does not restore shared protection.
5. Restore Redis connectivity and verify that both replicas can consume one
   shared window. The clients reconnect without making Redis a domain
   dependency.
6. Treat all pre-restart rate-limit windows as reset. A post-restart burst is
   possible; rely on the trusted ingress as an additional protection layer.
7. Verify PostgreSQL invariants independently. Never serve or reconstruct
   Product, Inventory, Content, reservation, or job-lease state from Redis.

Start the isolated two-replica topology with:

```powershell
docker compose -f docker-compose.yml -f docker-compose.multi-instance.yml up --build api-replica-a api-replica-b
```

Exercise the restart with:

```powershell
docker compose -f docker-compose.yml -f docker-compose.multi-instance.yml restart redis
```

Send one authenticated actor's high-risk requests alternately to ports 18001
and 18002 before and after the restart. Record the fail-policy responses during
the outage, the reset budget after recovery, and distinct Prometheus
`instance` series for both replicas.

## Signing-key compromise

1. Remove the compromised key from active and previous key sets.
2. Deploy a new strong secret and key ID to every API replica.
3. Restart/roll replicas so no verifier retains the old configuration.
4. Reissue trusted service tokens.
5. Review request IDs, actor IDs, JTI values, and privileged-route logs.

This immediately invalidates all tokens signed by the removed key. There is no
distributed JTI revocation store.

## Concurrency conflict

HTTP 409 `CONCURRENT_MODIFICATION` is a safe stale-write rejection. Reload the
current entity and retry the business decision; do not blindly replay the old
patch. Inventory reservation conflicts must re-read availability.

## Required recovery exercises

Before production release, execute and record:

- restore backup into a clean database;
- empty-to-head and populated migration upgrade;
- worker kill during handler execution and stale recovery;
- one API replica restart while another serves traffic;
- key rotation with an unexpired previous-key token;
- Redis unavailable and restart behavior across two API replicas, including
  fail decisions, reset non-canonical budgets, and per-instance metrics;
- dead-letter manual retry;
- rollback/revision recovery without rewriting history.
