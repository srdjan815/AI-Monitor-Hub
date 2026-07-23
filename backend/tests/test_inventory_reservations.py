from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest


API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(base_url=API_ROOT, timeout=10.0) as client:
        yield client


def test_inventory_reservation_lifecycle(
    api_client: httpx.Client,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    category_id = product_id = warehouse_id = inventory_id = None
    try:
        category = api_client.post(
            "/categories",
            json={
                "name": f"Reservation Category {suffix}",
                "code": f"reservation_category_{suffix}",
            },
        )
        assert category.status_code == 201
        category_id = category.json()["id"]
        product = api_client.post(
            "/products",
            json={
                "category_id": category_id,
                "name": f"Reservation Product {suffix}",
                "code": f"reservation_product_{suffix}",
                "sku": f"RES-{suffix}",
            },
        )
        assert product.status_code == 201
        product_id = product.json()["id"]
        warehouse = api_client.post(
            "/warehouses",
            json={
                "code": f"reservation_{suffix}",
                "name": f"Reservation Warehouse {suffix}",
            },
        )
        assert warehouse.status_code == 201
        warehouse_id = warehouse.json()["id"]
        inventory = api_client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity_on_hand": 100,
            },
        )
        assert inventory.status_code == 201
        inventory_id = inventory.json()["id"]

        missing_balance = api_client.post(
            "/inventory/reservations",
            json={
                "product_id": product_id,
                "warehouse_id": str(uuid.uuid4()),
                "quantity": 1,
            },
        )
        assert missing_balance.status_code == 404
        assert api_client.post(
            "/inventory/reservations",
            json={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": 0,
            },
        ).status_code == 422
        assert api_client.post(
            "/inventory/reservations",
            json={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": 101,
            },
        ).status_code == 422

        external_reference = f"reservation-{suffix}"
        payload = {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "quantity": 40,
            "external_reference": external_reference,
            "reference_type": "TEST",
            "reference_id": suffix,
        }
        created = api_client.post(
            "/inventory/reservations", json=payload
        )
        assert created.status_code == 201
        reservation = created.json()
        assert reservation["reservation_number"].startswith("RES-")
        assert reservation["remaining_quantity"] == 40
        assert reservation["status"] == "ACTIVE"

        equivalent = api_client.post(
            "/inventory/reservations", json=payload
        )
        assert equivalent.status_code == 201
        assert equivalent.json()["id"] == reservation["id"]
        conflict = api_client.post(
            "/inventory/reservations",
            json={**payload, "quantity": 39},
        )
        assert conflict.status_code == 409
        current = api_client.get(f"/inventory/{inventory_id}").json()
        assert current["quantity_reserved"] == 40
        assert current["quantity_available"] == 60

        partial = api_client.post(
            f"/inventory/reservations/{reservation['id']}/fulfill",
            json={
                "quantity": 15,
                "external_reference": f"fulfill-{suffix}-1",
            },
        )
        assert partial.status_code == 200
        assert partial.json()["status"] == "PARTIALLY_FULFILLED"
        assert partial.json()["remaining_quantity"] == 25
        idempotent_fulfill = api_client.post(
            f"/inventory/reservations/{reservation['id']}/fulfill",
            json={
                "quantity": 15,
                "external_reference": f"fulfill-{suffix}-1",
            },
        )
        assert idempotent_fulfill.status_code == 200
        current = api_client.get(f"/inventory/{inventory_id}").json()
        assert current["quantity_on_hand"] == 85
        assert current["quantity_reserved"] == 25

        movements = api_client.get(
            "/inventory/movements",
            params={"external_reference": f"fulfill-{suffix}-1"},
        )
        assert movements.status_code == 200
        assert movements.json()["items"][0]["movement_type"] == "ISSUE"
        assert (
            movements.json()["items"][0]["reference_id"]
            == reservation["id"]
        )
        assert api_client.post(
            f"/inventory/reservations/{reservation['id']}/fulfill",
            json={"quantity": 26},
        ).status_code == 422

        released = api_client.post(
            f"/inventory/reservations/{reservation['id']}/release"
        )
        assert released.status_code == 200
        assert released.json()["status"] == "RELEASED"
        assert api_client.post(
            f"/inventory/reservations/{reservation['id']}/release"
        ).status_code == 409
        current = api_client.get(f"/inventory/{inventory_id}").json()
        assert current["quantity_reserved"] == 0

        cancel = api_client.post(
            "/inventory/reservations",
            json={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": 10,
            },
        ).json()
        cancelled = api_client.post(
            f"/inventory/reservations/{cancel['id']}/cancel"
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "CANCELLED"

        expired = api_client.post(
            "/inventory/reservations",
            json={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": 5,
                "expires_at": (
                    datetime.now(UTC) - timedelta(minutes=1)
                ).isoformat(),
            },
        ).json()
        future = api_client.post(
            "/inventory/reservations",
            json={
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "quantity": 5,
                "expires_at": (
                    datetime.now(UTC) + timedelta(days=1)
                ).isoformat(),
            },
        ).json()
        summary = api_client.post(
            "/inventory/reservations/expire", params={"limit": 1}
        )
        assert summary.status_code == 200
        assert summary.json() == {"processed": 1, "skipped": 0}
        assert api_client.get(
            f"/inventory/reservations/{expired['id']}"
        ).json()["status"] == "EXPIRED"
        assert api_client.get(
            f"/inventory/reservations/{future['id']}"
        ).json()["status"] == "ACTIVE"

        active = api_client.get(
            "/inventory/reservations",
            params={"product_id": product_id, "active_only": "true"},
        )
        assert active.status_code == 200
        assert {item["id"] for item in active.json()["items"]} == {
            future["id"]
        }
        all_rows = api_client.get(
            "/inventory/reservations",
            params={
                "product_id": product_id,
                "active_only": "false",
                "limit": 2,
                "offset": 0,
            },
        )
        assert all_rows.status_code == 200
        assert all_rows.json()["total"] == 4
        assert len(all_rows.json()["items"]) == 2
        assert api_client.get(
            f"/inventory/reservations/{uuid.uuid4()}"
        ).status_code == 404
    finally:
        if inventory_id is not None:
            api_client.delete(f"/inventory/{inventory_id}")
        if warehouse_id is not None:
            api_client.delete(f"/warehouses/{warehouse_id}")
        if product_id is not None:
            api_client.delete(f"/products/{product_id}")
        if category_id is not None:
            api_client.delete(f"/categories/{category_id}")
