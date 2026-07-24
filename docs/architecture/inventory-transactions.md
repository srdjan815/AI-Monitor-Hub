# Inventory transaction model

## Canonical state

`Inventory` is the current balance for one `(warehouse_id, product_id)` pair.
`InventoryMovement` is the immutable business history. `InventoryReservation`
is a stateful claim against available stock. Product never stores quantities.

The database constraints and service checks enforce:

```text
quantity_on_hand >= 0
quantity_reserved >= 0
quantity_reserved <= quantity_on_hand
quantity_available = quantity_on_hand - quantity_reserved
```

The warehouse/product pair is unique. Soft deletion changes `is_active`; it
does not erase movement or reservation history.

## Ownership

| Command | Transaction owner | Rows locked or mutated atomically |
|---|---|---|
| Warehouse create/update/deactivate | `WarehouseBalanceService` | Warehouse |
| Balance administration | `WarehouseBalanceService` | Inventory balance |
| Movement create/reverse | `InventoryMovementService` | affected balance(s), movement, reversal link |
| Reserve | `ReservationService` | balance, reservation |
| Release/cancel/expire | `ReservationService` | reservation, balance |
| Fulfill | `ReservationService` | reservation, balance, movement |

Repositories query and flush only. Services commit after every invariant is
valid, roll back every exception, and refresh returned entities after commit.

## Reservation sequence

```mermaid
sequenceDiagram
    participant API
    participant ReservationService
    participant PostgreSQL
    API->>ReservationService: reserve(product, warehouse, quantity, key)
    ReservationService->>PostgreSQL: lock balance FOR UPDATE
    ReservationService->>PostgreSQL: validate available >= quantity
    ReservationService->>PostgreSQL: add reservation; increment reserved
    ReservationService->>PostgreSQL: flush and commit
    PostgreSQL-->>API: refreshed reservation
```

Concurrent reservations serialize on the balance row. Optimistic version
columns additionally fence detached or stale updates. A unique idempotency key
prevents repeated movement/reservation submission from applying twice.

## Fulfillment

Fulfillment is one transaction:

1. lock the reservation and balance;
2. verify the reservation is active and has remaining quantity;
3. decrement reserved and on-hand quantities;
4. create the movement/history record;
5. transition the reservation;
6. flush, commit, and refresh.

No intermediate state is committed. A failure in any step rolls back the
balance, movement, and reservation together.

## Lock ordering

Multi-row work locks stable identifiers in deterministic order. New
multi-product operations must sort by `(warehouse_id, product_id, id)` before
locking. They may not lock in request order. This is the required deadlock
prevention rule for future transfer or batch reservation work.

## Isolation and scaling

Correctness relies on PostgreSQL row locks, uniqueness constraints, checks, and
version columns, not process-local locks. Multiple API or worker instances may
therefore share the same database. Redis is not part of Inventory correctness.
