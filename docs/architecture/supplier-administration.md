# Supplier Administration — Chapter 3.1

## Scope

Chapter 3.1 introduces Supplier master records and Supplier Contacts. It is the
first implementation slice of the approved Supplier Platform bounded context.
Foundation v1.0 remains frozen.

Implemented responsibilities:

- immutable UUID Supplier identity;
- concurrency-safe generated `SUP-000001` Supplier codes;
- Supplier and Contact CRUD;
- Supplier operational states `ACTIVE`, `INACTIVE`, and `SUSPENDED`;
- soft deletion;
- optimistic version checks on PATCH;
- active-identifier uniqueness;
- one active primary Contact per Supplier and Contact type;
- Supplier-specific read/write permissions;
- authenticated REST and OpenAPI surfaces.

## Explicit exclusions

This chapter does not implement source connections, connectors, file upload,
imports, raw storage, schema or mapping profiles, normalization, Supplier
Products, snapshots, warehouses, prices, deltas, incidents, notifications,
refresh scheduling, Matching, Catalog Product creation, Pricing, Inventory
mutations, AI, Publishing, ERP synchronization, or frontend code. No
placeholder table or route exists for those capabilities.

## Architecture

The module follows the frozen dependency direction:

```text
Supplier router -> SupplierService -> SupplierRepository -> PostgreSQL
```

The router owns HTTP transport and DTO conversion. The service owns validation,
state transitions, stable domain conflicts, commit, rollback, refresh, and
authenticated actor logging. The repository owns queries, row locks, mutation,
and `flush()` only.

The compatibility `router.py` aggregates separate Supplier and Contact routers.
Supplier and Contact command services are likewise separate, while shared
normalization and constraint validation live in `SupplierValidationService`.
Every implementation file remains below the Foundation decomposition limit.

Supplier Administration does not import Inventory or Product Content and does
not define or mutate Catalog Product.

## Identity and concurrency

`Supplier.id` is an immutable UUID. `Supplier.supplier_code` is produced by the
PostgreSQL `supplier_code_seq` sequence and formatted by the database as
`SUP-` plus a minimum six-digit number. Sequence gaps after rolled-back
transactions are valid and intentional; uniqueness and concurrency safety take
priority over gapless numbering. Downgrade removes the two Chapter 3.1 tables
before removing the sequence.

The initial Chapter migration creates the code as `VARCHAR(10)`. The Chapter
3.1 fix revision `e9f0a1b2c3d4` safely expands it to `VARCHAR(50)` without
changing generation or public formatting, avoiding a capacity failure after
the first 999,999 sequence values.

Supplier and Supplier Contact use SQLAlchemy optimistic versions. PATCH
requests include the expected `version`. A stale version returns a stable 409
domain conflict. Real mutations increment the version; no-change PATCH keeps
the current version.

## Deactivation and uniqueness

DELETE performs soft deletion. Supplier deactivation also changes its
operational status to `INACTIVE` but does not delete or deactivate historical
Contacts. Archived Suppliers and Contacts remain available through
`active_only=false`.

Tax identifiers and registration numbers are unique among active Suppliers
when present. Deactivated Suppliers no longer occupy those active-identity
constraints. Contact email and phone are optional individually, but at least
one is required. A PostgreSQL partial unique index permits only one active
primary Contact for each Supplier and Contact type.

## Permissions and API

The domain permissions are:

- `suppliers.read`;
- `suppliers.write`.

Supplier routes are registered through the protected API router and are
explicitly classified by the central permission policy. They never fall
through to Catalog permissions. The Swagger tag is
`supplier-administration`, with Serbian administrator-facing field, filter,
operation, concurrency, and soft-delete descriptions.
