# Attribute Orchestration

Attribute writes enter `AttributeMutationCoordinator`. It constructs the
platform and product-attribute services explicitly and injects a narrow
recalculation callback. `ProductAttributeService` no longer performs a local
import of `AttributePlatformService`, removing the hidden bidirectional service
cycle.

Base-value validation, normalization, persistence, derived recalculation,
history, and event creation share the caller-owned transaction. Recalculation
writes invoked by the platform service do not inject the callback again, which
prevents recursive traversal. A failure propagates to the service rollback
boundary; repositories only flush.

The coordinator is the supported mutation entry point for HTTP writes. Direct
service construction is retained for compatibility and read/query paths.
