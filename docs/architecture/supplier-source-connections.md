# Supplier Source Connections — Chapter 3.2

Chapter 3.2 adds administrative configuration for Supplier feed locations. It
does not acquire, download, parse, import, schedule, map, or normalize data.

## Architecture

The frozen dependency direction remains:

```text
Source router -> SupplierSourceService -> SupplierSourceRepository -> PostgreSQL
```

The service owns validation and transactions. The repository performs queries,
locking, mutations, and `flush()` only. Source files do not import Catalog,
Inventory, Product Content, network clients, parsers, or worker infrastructure.

## Configuration and secrets

Each of the ten source types has a strict Pydantic configuration model with
unknown fields forbidden and bounded values. Configuration is normalized before
it reaches JSONB. Credential-like fields are rejected.

The database stores only an opaque `secret_reference` using the `vault:`,
`env:`, or `secret:` schemes. API responses expose only
`has_secret_reference`; they never expose a reference value or resolved secret.
Secret resolution is reserved for approved future infrastructure.

The validation endpoint validates stored configuration and secret-reference
presence only. It performs no DNS lookup, external connection, request, file
access, or download. Persisted validation fields describe configuration
validation, not live connectivity.

## Identity and lifecycle

`supplier_source_code_seq` generates immutable, globally unique codes in the
form `SRC-000001`; gaps are intentional. The code column is `VARCHAR(50)`.
Downgrade removes `supplier_sources` before removing its dedicated sequence.

New sources are `DRAFT` or explicitly `INACTIVE`. Activation requires a valid
configuration, any required secret reference, and an active Supplier. DELETE is
an idempotent soft delete. Source type and source code are immutable, and PATCH
uses optimistic versions.

Active source names are case-insensitively unique per Supplier. The same name is
allowed for a different Supplier or after archival.

## Scope boundary

No acquisition, import, refresh, download, upload, preview, schema, mapping,
normalization, Supplier Product, snapshot, price, delta, incident, scheduler,
notification, Matching, Catalog, Inventory, AI, publishing, or ERP object or
endpoint is introduced.
