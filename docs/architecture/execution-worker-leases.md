# Execution Worker Leases

Claiming a job records worker identity, attempt number, and a random lease token.
Heartbeat and finalization use compare-and-set predicates over job ID, running
status, worker ID, lease token, and attempt. Recovery replaces the lease. A stale
worker therefore cannot mark a recovered attempt succeeded or failed.

The worker runs heartbeat concurrently with the handler and clears the lease
only through fenced success/failure transitions. Lease loss makes stale
completion a no-op and is logged. The schema addition is isolated in corrective
migration `e2f3a4b5c6d7_execution_job_leases.py`.

The worker races handler execution against heartbeat ownership. Lease loss sets
cooperative cancellation, cancels the local handler task, and prevents a stale
completion transaction. External effects still require handler-level
idempotency because delivery is at least once. Full state, retry, timeout,
cancellation, and dead-letter semantics are documented in
[`execution-state-machine.md`](execution-state-machine.md).
