# Supplier Acquisition Engine — Chapter 3.5

Chapter 3.5 extends the frozen Chapter 3.4 baseline at commit
`cc0982166104e2d4085fa04b668272e9df868eda`. It acquires supplier data,
validates it, applies the frozen mapping rules, and persists immutable staged
results. It does not create Catalog products, snapshots, deltas, or incidents.

## Reused frozen contracts

An Acquisition Run references the existing Supplier, Source Connection, active
Schema Profile and Fields, and compatible active Mapping Profile and Rules.
Those entities keep their existing ownership and lifecycle. Schema Fields and
Mapping Rules are loaded once for each run.

## Execution components

- The source adapter registry selects manual-upload or HTTP/API acquisition
  without transport logic in routers or services.
- `SecretResolver` resolves opaque secret references only at runtime. Resolved
  values are never stored or logged.
- `LocalArtifactStorage` uses a configurable root, generated server filenames,
  bounded size, atomic writes, path validation, and SHA-256 checksums.
- The parser registry supports CSV, XLSX, XML, and JSON. XML external entities
  are rejected and spreadsheet formulas are never evaluated.
- The mapping executor implements every transformation frozen in Chapter 3.4
  as deterministic, side-effect-free operations.

Manual CSV, XLSX, and XML uploads and HTTP/API JSON acquisition are implemented.
FTP, SFTP, Google Drive, and Email execution are explicitly deferred because
the frozen Source Connection contracts do not contain everything needed for a
safe runtime client. They return a stable unsupported-execution error.

## Lifecycle and transactions

Runs move from `PENDING` to `RUNNING`, then to `SUCCEEDED`,
`PARTIALLY_SUCCEEDED`, `FAILED`, or eligible `CANCELLED`. Terminal runs and
their staged results are immutable. Retry always creates a new run.

External acquisition and parsing are separated from database mutation phases.
Repositories only flush; services commit or roll back. Fatal errors are stored
as sanitized terminal failures. Optional idempotency is protected by a partial
unique database index for Source Connection and key.

## Staged-result contract

Raw and mapped records are stored in PostgreSQL JSONB without arbitrary text
truncation, preserving Unicode, line breaks, and HTML text. List endpoints omit
large payloads; record detail returns them. Structured issues refer to their
run, row, Schema Field, and Mapping Rule where applicable, but never contain
complete files, secrets, stack traces, or complete long descriptions.

An accepted staged record is the stable input contract for Chapter 3.6. It is
not a Product or Snapshot, and Chapter 3.6 may consume it without changing the
Chapter 3.5 tables.

## Explicit non-goals

Chapter 3.5 has no scheduler, queue, worker, background execution, snapshot
creation, delta calculation, incident creation, Catalog or Inventory writes,
or Admin UI.
