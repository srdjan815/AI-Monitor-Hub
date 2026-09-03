# Supplier Incident Center — Chapter 3.8

Incident Center synchronously converts persisted operational facts from
Acquisition, Snapshot and Delta into a normalized workflow. A Delta anomaly
signal remains an immutable fact; an Incident is the operational object used to
acknowledge, assign, investigate, resolve, dismiss, suppress and correlate that
fact. Incident processing never mutates Acquisition, Snapshot, Delta, Catalog or
Inventory.

## Classification and lifecycle

Source domains are ACQUISITION, SNAPSHOT, DELTA, SOURCE_CONNECTION, SCHEMA,
MAPPING, MANUAL and SYSTEM. Structured types preserve the accepted Chapter
3.5–3.7 failure and anomaly codes. Severity describes impact (INFO through
CRITICAL), while priority describes urgency (P4 through P1). Configurable
default due dates are four hours, one day, three days and seven days.

Controlled transitions are:

```
OPEN -> ACKNOWLEDGED | IN_PROGRESS | RESOLVED | DISMISSED | SUPPRESSED
ACKNOWLEDGED -> IN_PROGRESS | RESOLVED | DISMISSED | SUPPRESSED
IN_PROGRESS -> RESOLVED | DISMISSED | SUPPRESSED
RESOLVED | DISMISSED | SUPPRESSED -> OPEN
```

Resolution requires a code and summary. Dismissal and suppression require a
reason. Reopening retains prior resolution metadata. Assignment uses the
Foundation stateless authentication subject; Foundation has no persistent user
directory against which an “inactive user” could be queried.

Every occurrence and workflow mutation writes an immutable Incident Event in
the same service-owned transaction. Comments are bounded plain text and create
COMMENT_ADDED events. Correlation uses simple PARENT, CHILD and RELATED links;
Incidents are never destructively merged.

## Fingerprints, recurrence and suppression

Automated fingerprints contain Supplier, optional Source Connection, source
domain, Incident type and stable source entity identity. They exclude time,
status, occurrence count, assignment and comments. A PostgreSQL partial unique
index protects active fingerprints.

An active recurrence reuses the Incident, increments `occurrence_count`, updates
`last_detected_at` and appends OCCURRENCE. RESOLVED recurrence reopens the same
Incident. DISMISSED recurrence may create a new Incident. Active SUPPRESSED
recurrence remains suppressed while still recording occurrences. Once
`suppression_until` has expired, the next occurrence adds
SUPPRESSION_EXPIRED and REOPENED; no scheduler is required.

## Rules and safe evidence

Rules are typed data, never executable expressions. Precedence is Source
Connection, Supplier, global, then safe system default. Rules control enabled
signals, resulting severity, priority, thresholds, auto-reopen and suppression
compatibility. IMAGE_SET_CHANGED requires an explicit enabled rule by default.

Context is recursively bounded. Keys representing secrets, tokens,
authorization, credentials, cookies and passwords are redacted. Secret-like
string values are redacted as well. Large strings become SHA-256 hash, length
and a 240-character sanitized preview. Complete supplier files, external
exception bodies, stack traces and long descriptions are not copied.

Automated synchronization reads existing terminal status, sanitized failure
metadata and persisted anomaly signals. It does not reparse files, retry
Acquisition, restore Snapshot, recalculate Delta, download images or create
notifications. Repository methods flush only; services own commit and rollback;
routers contain no SQL; rule, fingerprint and sanitization helpers are
side-effect free.

Chapter 3.9 may expose approved Supplier API views over these stable contracts.
Email, Slack, SMS, webhooks, workers, queues, schedules, browser UI and all
Catalog/Inventory actions remain deferred.
