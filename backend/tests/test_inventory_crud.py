from __future__ import annotations

import uuid

import httpx
import pytest


API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(base_url=API_ROOT, timeout=10.0) as client:
        yield client


def item_ids(response: httpx.Response) -> set[str]:
    response.raise_for_status()
    return {item["id"] for item in response.json()["items"]}


def test_warehouses_crud(api_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:12]
    code = f"warehouse_{suffix}"
    warehouse_id: str | None = None

    try:
        created = api_client.post(
            "/warehouses",
            json={
                "code": code,
                "name": f"Disposable Warehouse {suffix}",
                "description": "Disposable test warehouse",
            },
        )
        assert created.status_code == 201
        warehouse = created.json()
        warehouse_id = warehouse["id"]
        assert warehouse["version"] == 1

        duplicate = api_client.post(
            "/warehouses",
            json={
                "code": code,
                "name": f"Duplicate Warehouse {suffix}",
            },
        )
        assert duplicate.status_code == 409

        fetched = api_client.get(f"/warehouses/{warehouse_id}")
        assert fetched.status_code == 200
        assert fetched.json()["code"] == code

        updated = api_client.patch(
            f"/warehouses/{warehouse_id}",
            json={"name": f"Disposable Warehouse Updated {suffix}"},
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 2

        missing_id = uuid.uuid4()
        assert api_client.get(f"/warehouses/{missing_id}").status_code == 404
        assert (
            api_client.patch(
                f"/warehouses/{missing_id}",
                json={"name": "Missing"},
            ).status_code
            == 404
        )

        deleted = api_client.delete(f"/warehouses/{warehouse_id}")
        assert deleted.status_code == 204

        inactive = api_client.get(f"/warehouses/{warehouse_id}")
        assert inactive.status_code == 200
        assert inactive.json()["is_active"] is False
        assert inactive.json()["version"] == 3

        assert warehouse_id not in item_ids(
            api_client.get("/warehouses", params={"limit": 500})
        )
        assert warehouse_id in item_ids(
            api_client.get(
                "/warehouses",
                params={"active_only": "false", "limit": 500},
            )
        )
    finally:
        if warehouse_id is not None:
            api_client.delete(f"/warehouses/{warehouse_id}")


def test_inventory_crud_and_validation(api_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:12]
    category_id: str | None = None
    product_id: str | None = None
    warehouse_id: str | None = None
    inventory_id: str | None = None

    try:
        category_response = api_client.post(
            "/categories",
            json={
                "name": f"Inventory Test Category {suffix}",
                "code": f"inventory_category_{suffix}",
            },
        )
        assert category_response.status_code == 201
        category_id = category_response.json()["id"]

        product_response = api_client.post(
            "/products",
            json={
                "category_id": category_id,
                "name": f"Inventory Test Product {suffix}",
                "code": f"inventory_product_{suffix}",
                "sku": f"INV-{suffix}",
            },
        )
        assert product_response.status_code == 201
        product_id = product_response.json()["id"]

        warehouse_response = api_client.post(
            "/warehouses",
            json={
                "code": f"inventory_warehouse_{suffix}",
                "name": f"Inventory Test Warehouse {suffix}",
            },
        )
        assert warehouse_response.status_code == 201
        warehouse_id = warehouse_response.json()["id"]

        missing_warehouse = api_client.post(
            "/inventory",
            json={
                "warehouse_id": str(uuid.uuid4()),
                "product_id": product_id,
            },
        )
        assert missing_warehouse.status_code == 404

        missing_product = api_client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": str(uuid.uuid4()),
            },
        )
        assert missing_product.status_code == 404

        negative = api_client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity_on_hand": -1,
            },
        )
        assert negative.status_code == 422

        over_reserved = api_client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity_on_hand": 5,
                "quantity_reserved": 6,
            },
        )
        assert over_reserved.status_code == 422

        created = api_client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity_on_hand": 20,
                "quantity_reserved": 4,
                "minimum_stock": 3,
                "reorder_point": 5,
            },
        )
        assert created.status_code == 201
        inventory = created.json()
        inventory_id = inventory["id"]
        assert inventory["quantity_available"] == 16
        assert inventory["version"] == 1

        duplicate = api_client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": product_id,
            },
        )
        assert duplicate.status_code == 409

        fetched = api_client.get(f"/inventory/{inventory_id}")
        assert fetched.status_code == 200

        invalid_update = api_client.patch(
            f"/inventory/{inventory_id}",
            json={"quantity_reserved": 21},
        )
        assert invalid_update.status_code == 422

        updated = api_client.patch(
            f"/inventory/{inventory_id}",
            json={
                "quantity_on_hand": 30,
                "quantity_reserved": 7,
                "reorder_point": 8,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["quantity_available"] == 23
        assert updated.json()["version"] == 2

        filtered = api_client.get(
            "/inventory",
            params={
                "warehouse_id": warehouse_id,
                "product_id": product_id,
            },
        )
        assert inventory_id in item_ids(filtered)

        missing_id = uuid.uuid4()
        assert api_client.get(f"/inventory/{missing_id}").status_code == 404
        assert (
            api_client.patch(
                f"/inventory/{missing_id}",
                json={"quantity_on_hand": 1},
            ).status_code
            == 404
        )

        deleted = api_client.delete(f"/inventory/{inventory_id}")
        assert deleted.status_code == 204

        inactive = api_client.get(f"/inventory/{inventory_id}")
        assert inactive.status_code == 200
        assert inactive.json()["is_active"] is False
        assert inactive.json()["version"] == 3

        assert inventory_id not in item_ids(
            api_client.get("/inventory", params={"limit": 500})
        )
        assert inventory_id in item_ids(
            api_client.get(
                "/inventory",
                params={"active_only": "false", "limit": 500},
            )
        )
    finally:
        if inventory_id is not None:
            api_client.delete(f"/inventory/{inventory_id}")
        if warehouse_id is not None:
            api_client.delete(f"/warehouses/{warehouse_id}")
        if product_id is not None:
            api_client.delete(f"/products/{product_id}")
        if category_id is not None:
            api_client.delete(f"/categories/{category_id}")
