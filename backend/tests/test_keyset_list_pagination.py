from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.core.pagination import encode_cursor
from app.core.security import create_access_token


API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with httpx.Client(
        base_url=API_ROOT,
        timeout=30.0,
        headers={"Authorization": f"Bearer {create_access_token('keyset-tests')}"},
    ) as api_client:
        yield api_client


def _suffix() -> str:
    return uuid.uuid4().hex


def _active_category_id(client: httpx.Client) -> str:
    response = client.get("/categories", params={"limit": 1})
    response.raise_for_status()
    return response.json()["items"][0]["id"]


def _create_product(
    client: httpx.Client,
    category_id: str,
    token: str,
) -> dict[str, Any]:
    response = client.post(
        "/products",
        json={
            "category_id": category_id,
            "name": f"Disposable cursor product {token}",
            "code": f"cursor_product_{token}",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _collect_snapshot(
    client: httpx.Client,
    path: str,
    params: dict[str, Any],
    first: httpx.Response,
) -> list[str]:
    first.raise_for_status()
    snapshot_at = first.headers["x-snapshot-at"]
    expected_total = first.json()["total"]
    identifiers: list[str] = []
    response = first

    while True:
        assert response.headers["x-snapshot-at"] == snapshot_at
        identifiers.extend(item["id"] for item in response.json()["items"])
        cursor = response.headers.get("x-next-cursor")
        if cursor is None:
            break
        response = client.get(path, params={**params, "cursor": cursor})
        response.raise_for_status()

    assert len(identifiers) == expected_total
    assert len(identifiers) == len(set(identifiers))
    return identifiers


def _assert_invalid_cursor(response: httpx.Response) -> None:
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "INVALID_CURSOR"


def _tamper(cursor: str) -> str:
    replacement = "A" if cursor[-1] != "A" else "B"
    return f"{cursor[:-1]}{replacement}"


def test_product_cursor_is_signed_filter_bound_and_snapshot_stable(
    client: httpx.Client,
) -> None:
    category_id = _active_category_id(client)
    created_ids: list[str] = []

    try:
        for _ in range(3):
            product = _create_product(client, category_id, _suffix())
            created_ids.append(product["id"])

        count_response = client.get(
            "/products",
            params={"active_only": "false", "limit": 1},
        )
        count_response.raise_for_status()
        assert "x-snapshot-at" not in count_response.headers
        total = count_response.json()["total"]
        limit = min(500, total - 1)
        params = {
            "active_only": "false",
            "limit": limit,
            "pagination": "cursor",
        }
        first = client.get("/products", params=params)
        first.raise_for_status()
        cursor = first.headers.get("x-next-cursor")
        assert cursor

        inserted = _create_product(client, category_id, _suffix())
        created_ids.append(inserted["id"])

        implicit_cursor_mode = client.get(
            "/products",
            params={
                "active_only": "false",
                "limit": limit,
                "cursor": cursor,
            },
        )
        assert implicit_cursor_mode.status_code == 200
        assert (
            implicit_cursor_mode.headers["x-snapshot-at"]
            == first.headers["x-snapshot-at"]
        )

        identifiers = _collect_snapshot(client, "/products", params, first)
        assert inserted["id"] not in identifiers

        _assert_invalid_cursor(
            client.get(
                "/products",
                params={**params, "cursor": _tamper(cursor)},
            )
        )
        _assert_invalid_cursor(
            client.get(
                "/products",
                params={
                    **params,
                    "active_only": "true",
                    "cursor": cursor,
                },
            )
        )
        naive_cursor = encode_cursor(
            "catalog.products",
            {
                "active_only": False,
                "limit": limit,
                "pagination": "cursor",
                "order": "created_at_desc,id_desc",
            },
            [
                "2026-01-01T00:00:00",
                str(uuid.uuid4()),
                "2026-01-01T00:00:00",
            ],
        )
        _assert_invalid_cursor(
            client.get(
                "/products",
                params={**params, "cursor": naive_cursor},
            )
        )
        _assert_invalid_cursor(
            client.get(
                "/products",
                params={**params, "cursor": cursor, "offset": 1},
            )
        )
        _assert_invalid_cursor(
            client.get(
                "/products",
                params={
                    **params,
                    "pagination": "offset",
                    "cursor": cursor,
                },
            )
        )
    finally:
        for product_id in created_ids:
            client.delete(f"/products/{product_id}")


def test_inventory_lists_use_stable_keysets_and_snapshot_boundaries(
    client: httpx.Client,
) -> None:
    suffix = _suffix()
    category_id = _active_category_id(client)
    product_ids: list[str] = []
    inventory_ids: list[str] = []
    reservation_ids: list[str] = []
    warehouse_id: str | None = None

    try:
        warehouse = client.post(
            "/warehouses",
            json={
                "code": f"cursor_warehouse_{suffix}",
                "name": f"Disposable cursor warehouse {suffix}",
            },
        )
        assert warehouse.status_code == 201, warehouse.text
        warehouse_id = warehouse.json()["id"]

        for _ in range(4):
            product = _create_product(client, category_id, _suffix())
            product_ids.append(product["id"])
            inventory = client.post(
                "/inventory",
                json={
                    "warehouse_id": warehouse_id,
                    "product_id": product["id"],
                    "quantity_on_hand": 100,
                },
            )
            assert inventory.status_code == 201, inventory.text
            inventory_ids.append(inventory.json()["id"])

        balance_params = {
            "warehouse_id": warehouse_id,
            "active_only": "false",
            "limit": 2,
            "pagination": "cursor",
        }
        first_balance = client.get("/inventory", params=balance_params)
        first_balance.raise_for_status()
        balance_cursor = first_balance.headers.get("x-next-cursor")
        assert balance_cursor

        late_product = _create_product(client, category_id, _suffix())
        product_ids.append(late_product["id"])
        late_balance = client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": late_product["id"],
                "quantity_on_hand": 100,
            },
        )
        assert late_balance.status_code == 201, late_balance.text
        inventory_ids.append(late_balance.json()["id"])

        balance_ids = _collect_snapshot(
            client,
            "/inventory",
            balance_params,
            first_balance,
        )
        assert late_balance.json()["id"] not in balance_ids
        _assert_invalid_cursor(
            client.get(
                "/inventory",
                params={
                    **balance_params,
                    "product_id": product_ids[0],
                    "cursor": balance_cursor,
                },
            )
        )

        for _ in range(3):
            movement = client.post(
                "/inventory/movements",
                json={
                    "movement_type": "RECEIPT",
                    "product_id": product_ids[0],
                    "destination_warehouse_id": warehouse_id,
                    "quantity": 1,
                    "external_reference": f"cursor-movement-{_suffix()}",
                },
            )
            assert movement.status_code == 201, movement.text

        movement_params = {
            "product_id": product_ids[0],
            "limit": 2,
            "pagination": "cursor",
        }
        first_movement = client.get(
            "/inventory/movements",
            params=movement_params,
        )
        first_movement.raise_for_status()
        assert first_movement.headers.get("x-next-cursor")
        late_movement = client.post(
            "/inventory/movements",
            json={
                "movement_type": "RECEIPT",
                "product_id": product_ids[0],
                "destination_warehouse_id": warehouse_id,
                "quantity": 1,
                "external_reference": f"cursor-movement-{_suffix()}",
            },
        )
        assert late_movement.status_code == 201, late_movement.text
        movement_ids = _collect_snapshot(
            client,
            "/inventory/movements",
            movement_params,
            first_movement,
        )
        assert late_movement.json()["id"] not in movement_ids

        for _ in range(3):
            reservation = client.post(
                "/inventory/reservations",
                json={
                    "product_id": product_ids[1],
                    "warehouse_id": warehouse_id,
                    "quantity": 1,
                    "external_reference": f"cursor-reservation-{_suffix()}",
                },
            )
            assert reservation.status_code == 201, reservation.text
            reservation_ids.append(reservation.json()["id"])

        reservation_params = {
            "product_id": product_ids[1],
            "active_only": "false",
            "limit": 2,
            "pagination": "cursor",
        }
        first_reservation = client.get(
            "/inventory/reservations",
            params=reservation_params,
        )
        first_reservation.raise_for_status()
        assert first_reservation.headers.get("x-next-cursor")
        late_reservation = client.post(
            "/inventory/reservations",
            json={
                "product_id": product_ids[1],
                "warehouse_id": warehouse_id,
                "quantity": 1,
                "external_reference": f"cursor-reservation-{_suffix()}",
            },
        )
        assert late_reservation.status_code == 201, late_reservation.text
        reservation_ids.append(late_reservation.json()["id"])
        reservation_ids_at_snapshot = _collect_snapshot(
            client,
            "/inventory/reservations",
            reservation_params,
            first_reservation,
        )
        assert late_reservation.json()["id"] not in reservation_ids_at_snapshot

        warehouses = client.get(
            "/warehouses",
            params={
                "active_only": "false",
                "limit": 500,
                "pagination": "cursor",
            },
        )
        warehouses.raise_for_status()
        assert warehouses.headers["x-snapshot-at"]
    finally:
        for reservation_id in reservation_ids:
            client.post(f"/inventory/reservations/{reservation_id}/cancel")
        for inventory_id in inventory_ids:
            client.delete(f"/inventory/{inventory_id}")
        if warehouse_id is not None:
            client.delete(f"/warehouses/{warehouse_id}")
        for product_id in product_ids:
            client.delete(f"/products/{product_id}")


def test_job_cursor_is_signed_filter_bound_and_snapshot_stable(
    client: httpx.Client,
) -> None:
    suffix = _suffix()
    queue = f"cursor-{suffix}"
    created_ids: list[str] = []

    def enqueue() -> dict[str, Any]:
        response = client.post(
            "/jobs",
            json={
                "job_type": "noop",
                "queue": queue,
                "available_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "idempotency_key": f"{queue}-{_suffix()}",
                "payload": {"test": suffix},
            },
        )
        assert response.status_code == 202, response.text
        created_ids.append(response.json()["id"])
        return response.json()

    try:
        initial = [enqueue() for _ in range(3)]
        params = {
            "queue": queue,
            "limit": 2,
            "pagination": "cursor",
        }
        first = client.get("/jobs", params=params)
        first.raise_for_status()
        cursor = first.headers.get("x-next-cursor")
        assert cursor
        assert first.json()["total"] == 3

        late = enqueue()
        second = client.get(
            "/jobs",
            params={**params, "cursor": cursor},
        )
        second.raise_for_status()
        assert second.headers["x-snapshot-at"] == first.headers["x-snapshot-at"]
        assert second.json()["total"] == 3

        identifiers = [
            *(item["id"] for item in first.json()["items"]),
            *(item["id"] for item in second.json()["items"]),
        ]
        assert len(identifiers) == len(set(identifiers)) == 3
        assert set(identifiers) == {item["id"] for item in initial}
        assert late["id"] not in identifiers

        _assert_invalid_cursor(
            client.get(
                "/jobs",
                params={**params, "cursor": _tamper(cursor)},
            )
        )
        _assert_invalid_cursor(
            client.get(
                "/jobs",
                params={
                    **params,
                    "queue": f"{queue}-changed",
                    "cursor": cursor,
                },
            )
        )
        _assert_invalid_cursor(
            client.get(
                "/jobs",
                params={**params, "cursor": cursor, "offset": 1},
            )
        )
    finally:
        for job_id in created_ids:
            client.post(f"/jobs/{job_id}/cancel")
