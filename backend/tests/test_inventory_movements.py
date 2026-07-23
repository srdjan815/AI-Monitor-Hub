from __future__ import annotations

import uuid

import httpx
import pytest


API_ROOT = "http://localhost:8000/api/v1"


@pytest.fixture
def api_client() -> httpx.Client:
    with httpx.Client(base_url=API_ROOT, timeout=10.0) as client:
        yield client


def create_movement(
    client: httpx.Client,
    *,
    movement_type: str,
    product_id: str,
    quantity: int,
    source_warehouse_id: str | None = None,
    destination_warehouse_id: str | None = None,
    external_reference: str | None = None,
) -> httpx.Response:
    return client.post(
        "/inventory/movements",
        json={
            "movement_type": movement_type,
            "product_id": product_id,
            "source_warehouse_id": source_warehouse_id,
            "destination_warehouse_id": destination_warehouse_id,
            "quantity": quantity,
            "external_reference": external_reference,
        },
    )


def balance(
    client: httpx.Client,
    warehouse_id: str,
    product_id: str,
) -> dict | None:
    response = client.get(
        "/inventory",
        params={
            "warehouse_id": warehouse_id,
            "product_id": product_id,
            "active_only": "false",
        },
    )
    response.raise_for_status()
    items = response.json()["items"]
    return items[0] if items else None


def reverse(client: httpx.Client, movement_id: str) -> httpx.Response:
    return client.post(f"/inventory/movements/{movement_id}/reverse")


def test_inventory_movement_ledger(api_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:12]
    category_id: str | None = None
    product_id: str | None = None
    warehouse_a: str | None = None
    warehouse_b: str | None = None
    inactive_warehouse: str | None = None

    try:
        category = api_client.post(
            "/categories",
            json={
                "name": f"Movement Category {suffix}",
                "code": f"movement_category_{suffix}",
            },
        )
        assert category.status_code == 201
        category_id = category.json()["id"]

        product = api_client.post(
            "/products",
            json={
                "category_id": category_id,
                "name": f"Movement Product {suffix}",
                "code": f"movement_product_{suffix}",
                "sku": f"MOV-{suffix}",
            },
        )
        assert product.status_code == 201
        product_id = product.json()["id"]

        first_warehouse = api_client.post(
            "/warehouses",
            json={
                "code": f"movement_a_{suffix}",
                "name": f"Movement Warehouse A {suffix}",
            },
        )
        second_warehouse = api_client.post(
            "/warehouses",
            json={
                "code": f"movement_b_{suffix}",
                "name": f"Movement Warehouse B {suffix}",
            },
        )
        assert first_warehouse.status_code == 201
        assert second_warehouse.status_code == 201
        warehouse_a = first_warehouse.json()["id"]
        warehouse_b = second_warehouse.json()["id"]

        missing_product = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=str(uuid.uuid4()),
            destination_warehouse_id=warehouse_a,
            quantity=1,
        )
        assert missing_product.status_code == 404

        missing_warehouse = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=product_id,
            destination_warehouse_id=str(uuid.uuid4()),
            quantity=1,
        )
        assert missing_warehouse.status_code == 404

        invalid_combination = create_movement(
            api_client,
            movement_type="TRANSFER",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            destination_warehouse_id=warehouse_a,
            quantity=1,
        )
        assert invalid_combination.status_code == 422

        missing_issue_balance = create_movement(
            api_client,
            movement_type="ISSUE",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            quantity=1,
        )
        assert missing_issue_balance.status_code == 422

        external_reference = f"receipt-{suffix}"
        receipt = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=product_id,
            destination_warehouse_id=warehouse_a,
            quantity=100,
            external_reference=external_reference,
        )
        assert receipt.status_code == 201
        receipt_data = receipt.json()
        assert receipt_data["movement_type"] == "RECEIPT"
        assert receipt_data["movement_number"].startswith("MOV-")
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 100

        conflicting_retry = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=product_id,
            destination_warehouse_id=warehouse_a,
            quantity=99,
            external_reference=external_reference,
        )
        assert conflicting_retry.status_code == 409
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 100

        idempotent = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=product_id,
            destination_warehouse_id=warehouse_a,
            quantity=100,
            external_reference=external_reference,
        )
        assert idempotent.status_code == 201
        assert idempotent.json()["id"] == receipt_data["id"]
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 100

        issue = create_movement(
            api_client,
            movement_type="ISSUE",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            quantity=10,
        )
        assert issue.status_code == 201
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 90
        assert reverse(api_client, issue.json()["id"]).status_code == 201
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 100

        adjustment_out = create_movement(
            api_client,
            movement_type="ADJUSTMENT_OUT",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            quantity=5,
        )
        assert adjustment_out.status_code == 201
        assert (
            reverse(api_client, adjustment_out.json()["id"]).status_code
            == 201
        )

        adjustment_in = create_movement(
            api_client,
            movement_type="ADJUSTMENT_IN",
            product_id=product_id,
            destination_warehouse_id=warehouse_a,
            quantity=5,
        )
        assert adjustment_in.status_code == 201
        assert (
            reverse(api_client, adjustment_in.json()["id"]).status_code
            == 201
        )
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 100

        transfer = create_movement(
            api_client,
            movement_type="TRANSFER",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            destination_warehouse_id=warehouse_b,
            quantity=20,
        )
        assert transfer.status_code == 201
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 80
        assert balance(api_client, warehouse_b, product_id)[
            "quantity_on_hand"
        ] == 20
        assert reverse(api_client, transfer.json()["id"]).status_code == 201
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 100
        assert balance(api_client, warehouse_b, product_id)[
            "quantity_on_hand"
        ] == 0

        insufficient = create_movement(
            api_client,
            movement_type="ISSUE",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            quantity=101,
        )
        assert insufficient.status_code == 422

        current_balance = balance(api_client, warehouse_a, product_id)
        reserved = api_client.patch(
            f"/inventory/{current_balance['id']}",
            json={"quantity_reserved": 95},
        )
        assert reserved.status_code == 200
        reserved_failure = create_movement(
            api_client,
            movement_type="ISSUE",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            quantity=10,
        )
        assert reserved_failure.status_code == 422
        api_client.patch(
            f"/inventory/{current_balance['id']}",
            json={"quantity_reserved": 0},
        )

        fetched = api_client.get(
            f"/inventory/movements/{receipt_data['id']}"
        )
        assert fetched.status_code == 200
        assert fetched.json()["id"] == receipt_data["id"]
        assert (
            api_client.patch(
                f"/inventory/movements/{receipt_data['id']}",
                json={"quantity": 1},
            ).status_code
            == 405
        )
        assert (
            api_client.delete(
                f"/inventory/movements/{receipt_data['id']}"
            ).status_code
            == 405
        )

        filtered = api_client.get(
            "/inventory/movements",
            params={
                "movement_type": "RECEIPT",
                "product_id": product_id,
                "warehouse_id": warehouse_a,
                "external_reference": external_reference,
                "limit": 1,
                "offset": 0,
            },
        )
        assert filtered.status_code == 200
        assert filtered.json()["items"][0]["id"] == receipt_data["id"]

        receipt_reversal = reverse(api_client, receipt_data["id"])
        assert receipt_reversal.status_code == 201
        assert balance(api_client, warehouse_a, product_id)[
            "quantity_on_hand"
        ] == 0
        assert reverse(api_client, receipt_data["id"]).status_code == 409

        rollback_receipt = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=product_id,
            destination_warehouse_id=warehouse_a,
            quantity=10,
        )
        assert rollback_receipt.status_code == 201
        consume = create_movement(
            api_client,
            movement_type="ISSUE",
            product_id=product_id,
            source_warehouse_id=warehouse_a,
            quantity=10,
        )
        assert consume.status_code == 201
        failed_reversal = reverse(
            api_client,
            rollback_receipt.json()["id"],
        )
        assert failed_reversal.status_code == 422
        original_after_failure = api_client.get(
            f"/inventory/movements/{rollback_receipt.json()['id']}"
        )
        assert original_after_failure.json()["is_reversed"] is False

        inactive_location = api_client.post(
            "/warehouses",
            json={
                "code": f"inactive_movement_{suffix}",
                "name": f"Inactive Movement Warehouse {suffix}",
            },
        )
        assert inactive_location.status_code == 201
        inactive_warehouse = inactive_location.json()["id"]
        api_client.delete(f"/warehouses/{inactive_warehouse}")
        inactive_warehouse_result = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=product_id,
            destination_warehouse_id=inactive_warehouse,
            quantity=1,
        )
        assert inactive_warehouse_result.status_code == 422

        api_client.delete(f"/products/{product_id}")
        inactive_product_result = create_movement(
            api_client,
            movement_type="RECEIPT",
            product_id=product_id,
            destination_warehouse_id=warehouse_a,
            quantity=1,
        )
        assert inactive_product_result.status_code == 422
    finally:
        for warehouse_id in (warehouse_a, warehouse_b, inactive_warehouse):
            if warehouse_id is not None:
                balances = api_client.get(
                    "/inventory",
                    params={
                        "warehouse_id": warehouse_id,
                        "active_only": "false",
                        "limit": 500,
                    },
                )
                if balances.status_code == 200:
                    for item in balances.json()["items"]:
                        api_client.delete(f"/inventory/{item['id']}")
                api_client.delete(f"/warehouses/{warehouse_id}")
        if product_id is not None:
            api_client.delete(f"/products/{product_id}")
        if category_id is not None:
            api_client.delete(f"/categories/{category_id}")
