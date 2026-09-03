# Supplier Snapshot Engine — Chapter 3.6

Chapter 3.6 consumes accepted staged records from the frozen Chapter 3.5
Acquisition Engine. A staged record is the validated result of one import
execution; a Snapshot Item is its immutable point-in-time mapped representation
for historical review and future Delta processing.

## Lifecycle and identity

One Acquisition Run can own at most one canonical Snapshot. Only `SUCCEEDED`
and `PARTIALLY_SUCCEEDED` runs are eligible, and only accepted staged records
become Items. A build moves from `BUILDING` to `READY` or `FAILED`. READY
identity and Items have no update or delete API.

Physical location is independent of business status:

- `ONLINE`: Item payload is available in PostgreSQL.
- `ARCHIVED`: verified payload is external and Item rows have been offloaded.
- `RESTORING`: synchronous restoration is in progress.

Snapshot and Item fingerprints use canonical, sorted UTF-8 JSON. Generated
database IDs, timestamps, archive paths, and storage metadata are excluded from
content fingerprints. Chapter 3.7 may use Item fingerprints as an optimization,
but Chapter 3.6 performs no Delta calculation.

## Data and supplier image evidence

Snapshot Items store mapped data as JSONB, preserving long descriptions,
Unicode, line breaks, valid HTML text, nullable values, and heterogeneous
supplier attributes. Recognized supplier image attributes are normalized into
ordered `source_image_links`. Exact duplicate URLs are removed; unsafe schemes
are excluded. The engine never calls image URLs and never stores image binaries.

## Portable archive format

Archive format version 1 is a UTF-8 ZIP containing:

- `manifest.json`
- `snapshot.json`
- `snapshot_items.jsonl`
- `checksums.json`
- optional `acquisition_artifact.bin`

JSONL permits incremental serialization. The manifest records Supplier, Source,
schema and mapping versions, Snapshot identity and fingerprint, Item count,
format versions, and per-file SHA-256 checksums. Resolved secrets are never
included. The original Acquisition artifact is read through the frozen Chapter
3.5 storage abstraction and included only after its checksum is verified.

The filesystem implementation uses a configured allowed archive root,
generated filenames, atomic finalization, path checks, free-space and size
limits, and no overwrite. USB, HDD, SSD, or network storage must already be
mounted by the operating system under that configured location. The application
does not mount hardware and never accepts an unrestricted API filesystem path.
Cloud archive destinations are deferred.

## Export, offload, and restoration

Export and offload are separate operations and permissions. Export writes,
reopens, and verifies the package, registers durable archive metadata, and
leaves the Snapshot ONLINE. Confirmed offload requires the exact verified
reference and checksum, re-verifies the readable package, checks legal hold and
preserve-online policy, deletes heavy Item rows, and changes storage state to
ARCHIVED. Snapshot identity, counts, fingerprints, archive metadata, retention
metadata, and audit timestamps remain in PostgreSQL.

Restoration verifies archive checksum, ZIP member safety, format compatibility,
Snapshot identity, file checksums, Item count, and fingerprints. It restores
the same Item and Snapshot identities, then returns the Snapshot to ONLINE. A
failed restoration cannot leave a false ONLINE state or partial final payload.

Candidate preview supports Supplier, Source, date interval, older-than,
storage-state, and bounded selection. It reports estimated Item and JSONB
payload sizes plus explicit exclusions. Legal hold always prevents offload.
Preserve-online excludes a candidate unless explicitly overridden by an
authorized request. No automatic retention schedule or age-based deletion is
implemented.

Deleting PostgreSQL rows reduces active logical payload; ordinary PostgreSQL
VACUUM behavior remains an operational concern before filesystem space is
reported as reclaimed. The application never runs `VACUUM FULL`.

## Transaction boundaries and non-goals

Routers call services, services own commits and rollbacks, repositories flush,
and archive storage/serialization never owns a database transaction. Slow file
export occurs outside a long-lived mutation transaction, and verified export is
durably distinct from completed offload.

Chapter 3.6 does not parse supplier files, call Source Adapters, execute mapping,
download images, calculate Deltas, create Incidents, write Catalog or Inventory,
schedule work, run background workers, or implement Admin UI. READY Items and
their fingerprints are the immutable input contract for Chapter 3.7.
