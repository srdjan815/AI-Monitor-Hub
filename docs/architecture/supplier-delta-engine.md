# Supplier Delta Engine — Chapter 3.7

Supplier Delta Engine synchronously compares two immutable, compatible Chapter
3.6 Snapshots and persists factual differences. A Delta fact is not a Catalog
change, and an anomaly signal is not an Incident.

## Consumed Snapshot contracts

Both Snapshots must be distinct, READY, ONLINE, owned by the same Supplier and
Source Connection, and supplied in chronological order. ARCHIVED payload is
never interpreted as an empty Snapshot: calculation returns
`SNAPSHOT_RESTORATION_REQUIRED`, and Chapter 3.6 restore remains explicit.
Snapshot and Item content is never mutated.

Items match by non-empty `source_key`, then `source_identifier`. Row number,
database ID, ordering, names, descriptions, prices, and fuzzy similarity are
never identities. A missing or duplicate identity fails the complete run rather
than fabricating a match.

Stored Chapter 3.6 Item fingerprints provide the unchanged fast path. Every
loaded Item is independently fingerprint-verified before comparison. A mismatch
fails with `SNAPSHOT_INTEGRITY_FAILURE`; the Snapshot is not repaired.

## Classification and comparison

Identity present only in the current Snapshot is ADDED; only in the previous is
REMOVED. A matched equal fingerprint increments the unchanged statistic.
Matched unequal fingerprints are compared recursively and become MODIFIED.
Dictionary ordering is irrelevant, array ordering is significant, and missing
is distinct from null. Types, Unicode, HTML, multiline strings and meaningful
whitespace are preserved. Decimal metadata uses `Decimal`, never binary
floating-point arithmetic.

Price and stock roles are factual classifications over normalized mapped
fields. No currency conversion, VAT, margin, rebate, costing, or Inventory
mutation occurs. Supplier image-link arrays are compared as stored; no external
request is made and no image binary is downloaded or stored.

Large values remain owned by immutable Snapshot Items. Field changes contain
SHA-256 hashes and sanitized previews bounded to 240 characters. Delta tables do
not duplicate full historical `mapped_data`, image arrays, files, or long
descriptions.

## Invariants and lifecycle

Comparison version 1 satisfies:

```
previous_total = removed + modified + unchanged
current_total  = added   + modified + unchanged
```

A run moves PENDING → RUNNING → SUCCEEDED or FAILED. Eligible work can be
cancelled before finalization; retry creates a new run. A partial unique index
allows one canonical SUCCEEDED result per ordered Snapshot pair and comparison
version. Terminal results are immutable through the public API.

Repositories flush only. Services own commit and rollback. Routers contain no
SQL, while canonical comparison and anomaly helpers are side-effect free.
Fingerprint equality avoids deep comparison, results are inserted in sets, and
list APIs are bounded and deterministic.

Persisted anomaly signals describe schema/mapping version changes and bounded
ratio thresholds. Chapter 3.8 may consume these facts, but Chapter 3.7 creates
no Incident, assignment, notification, alert, schedule, worker, Catalog Product,
or Inventory record.
