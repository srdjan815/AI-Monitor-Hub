# Cache strategy

## Current decision

No cache participates in canonical correctness. PostgreSQL remains authoritative
for Catalog, Product Attributes, Product Content, Inventory, and Execution.
The resolved-attribute problem was corrected with projection, filtering,
pagination, and streaming before considering cache.

The reference dataset did not prove a read-path bottleneck that justifies
shipping a mutable Redis cache in this foundation sprint. Therefore no
cross-process domain cache was added. This avoids stale Product, stock,
revision, prompt, or formula state and keeps the system correct when Redis is
unavailable.

Rate-limit counters are operational protection, not a domain cache. The memory
backend keeps them in one process; the Redis backend shares opaque,
fixed-window counters across API replicas. Both are bounded by active
`(policy, identity)` entries and neither affects domain correctness.

Prometheus metrics remain process-local even when the limiter uses Redis.
Redis unavailability follows the documented rate-limit fail policy. Redis
restart is treated as resetting non-canonical budgets; it must never trigger
domain reconstruction, invalidate PostgreSQL state, or serve stale domain
values.

## Approved future candidates

| Candidate | Key | Staleness | Invalidation | Maximum |
|---|---|---|---|---|
| Attribute definition metadata | schema version + definition ID/version | seconds | definition update/deactivate | bounded LRU |
| Resolved layout metadata | category/template/family versions + scope | seconds | assignment/template/family event | bounded LRU/Redis |
| Content type/language reference data | entity version | minutes | configuration mutation | small bounded LRU |
| Active prompt | content/attribute type + active version | seconds | prompt activation | small bounded LRU |
| Scoring policy | policy ID/version | seconds | policy mutation | small bounded LRU |

Canonical values, inventory balances, reservations, job leases, and current
revision flags are not approved cache targets.

## Required cache contract

Any future cache change must define and test:

- exact key and serialization version;
- tenant/actor dimension if introduced;
- TTL and maximum entries/bytes;
- mutation invalidation event;
- acceptable stale interval;
- single-flight or stampede control;
- hit, miss, eviction, and failure metrics;
- behavior when Redis is unavailable;
- proof that bypassing the cache returns the same answer.

Cache fills may be duplicated; correctness may not depend on a process-local
lock. A serialization-version mismatch is a miss, never a partially decoded
value.
