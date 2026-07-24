from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio

from app.core.security import create_access_token


API_ROOT = "http://localhost:8000/api/v1"
pytestmark = pytest.mark.asyncio(loop_scope="session")


@dataclass(slots=True)
class StockContext:
    category_id: str
    product_ids: list[str]
    warehouse_ids: list[str]
    inventory_ids: dict[tuple[str, str], str]


async def create_context(
    client: httpx.AsyncClient,
    *,
    product_count: int = 1,
    warehouse_count: int = 2,
    quantity: int = 100,
) -> StockContext:
    suffix = uuid.uuid4().hex
    category_response = await client.post(
        "/categories",
        json={
            "name": f"Inventory race category {suffix}",
            "code": f"inventory_race_category_{suffix}",
        },
    )
    assert category_response.status_code == 201, category_response.text
    category_id = category_response.json()["id"]

    product_ids: list[str] = []
    for index in range(product_count):
        response = await client.post(
            "/products",
            json={
                "category_id": category_id,
                "name": f"Inventory race product {index} {suffix}",
                "code": f"inventory_race_product_{index}_{suffix}",
            },
        )
        assert response.status_code == 201, response.text
        product_ids.append(response.json()["id"])

    warehouse_ids: list[str] = []
    for index in range(warehouse_count):
        response = await client.post(
            "/warehouses",
            json={
                "name": f"Inventory race warehouse {index} {suffix}",
                "code": f"inventory_race_warehouse_{index}_{suffix}",
            },
        )
        assert response.status_code == 201, response.text
        warehouse_ids.append(response.json()["id"])

    inventory_ids: dict[tuple[str, str], str] = {}
    for product_id in product_ids:
        for warehouse_id in warehouse_ids:
            response = await client.post(
                "/inventory",
                json={
                    "warehouse_id": warehouse_id,
                    "product_id": product_id,
                    "quantity_on_hand": quantity,
                },
            )
            assert response.status_code == 201, response.text
            inventory_ids[(warehouse_id, product_id)] = response.json()["id"]

    return StockContext(
        category_id=category_id,
        product_ids=product_ids,
        warehouse_ids=warehouse_ids,
        inventory_ids=inventory_ids,
    )


async def cleanup_context(
    client: httpx.AsyncClient,
    context: StockContext,
) -> None:
    for inventory_id in context.inventory_ids.values():
        await client.delete(f"/inventory/{inventory_id}")
    for warehouse_id in context.warehouse_ids:
        await client.delete(f"/warehouses/{warehouse_id}")
    for product_id in context.product_ids:
        await client.delete(f"/products/{product_id}")
    await client.delete(f"/categories/{context.category_id}")


async def inventory(
    client: httpx.AsyncClient,
    context: StockContext,
    warehouse_id: str,
    product_id: str,
) -> dict:
    response = await client.get(
        f"/inventory/{context.inventory_ids[(warehouse_id, product_id)]}"
    )
    assert response.status_code == 200, response.text
    return response.json()


async def reserve(
    client: httpx.AsyncClient,
    *,
    product_id: str,
    warehouse_id: str,
    quantity: int,
    external_reference: str,
    start: asyncio.Event | None = None,
) -> httpx.Response:
    if start is not None:
        await start.wait()
    return await client.post(
        "/inventory/reservations",
        json={
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "quantity": quantity,
            "external_reference": external_reference,
        },
    )


async def movement(
    client: httpx.AsyncClient,
    *,
    movement_type: str,
    product_id: str,
    quantity: int,
    external_reference: str,
    source_warehouse_id: str | None = None,
    destination_warehouse_id: str | None = None,
    start: asyncio.Event | None = None,
) -> httpx.Response:
    if start is not None:
        await start.wait()
    return await client.post(
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


@pytest_asyncio.fixture(loop_scope="session")
async def race_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(
        base_url=API_ROOT,
        timeout=30.0,
        headers={"Authorization": f"Bearer {create_access_token('inventory-race')}"},
    ) as client:
        yield client


async def test_reservation_fulfillment_release_and_concurrent_fulfillment_matrix(
    race_client: httpx.AsyncClient,
) -> None:
    context = await create_context(race_client, quantity=100)
    product_id = context.product_ids[0]
    warehouse_id = context.warehouse_ids[0]
    inventory_id = context.inventory_ids[(warehouse_id, product_id)]
    expected_on_hand = 100
    try:
        for iteration in range(10):
            created = await reserve(
                race_client,
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=2,
                external_reference=f"terminal-{iteration}-{uuid.uuid4().hex}",
            )
            assert created.status_code == 201, created.text
            reservation_id = created.json()["id"]
            start = asyncio.Event()

            async def release() -> httpx.Response:
                await start.wait()
                return await race_client.post(
                    f"/inventory/reservations/{reservation_id}/release"
                )

            async def fulfill() -> httpx.Response:
                await start.wait()
                return await race_client.post(
                    f"/inventory/reservations/{reservation_id}/fulfill",
                    json={
                        "quantity": 2,
                        "external_reference": (
                            f"terminal-fulfill-{iteration}-{uuid.uuid4().hex}"
                        ),
                    },
                )

            release_task = asyncio.create_task(release())
            fulfill_task = asyncio.create_task(fulfill())
            start.set()
            responses = await asyncio.gather(release_task, fulfill_task)
            assert sorted(response.status_code for response in responses) == [200, 409]
            final = await race_client.get(f"/inventory/reservations/{reservation_id}")
            assert final.status_code == 200
            assert final.json()["status"] in {"RELEASED", "FULFILLED"}
            assert final.json()["version"] == 2
            if final.json()["status"] == "FULFILLED":
                expected_on_hand -= 2
            current = await race_client.get(f"/inventory/{inventory_id}")
            assert current.status_code == 200
            assert current.json()["quantity_on_hand"] == expected_on_hand
            assert current.json()["quantity_reserved"] == 0

            created = await reserve(
                race_client,
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=2,
                external_reference=f"double-fulfill-{iteration}-{uuid.uuid4().hex}",
            )
            assert created.status_code == 201
            reservation_id = created.json()["id"]
            start = asyncio.Event()

            async def fulfill_once(token: str) -> httpx.Response:
                await start.wait()
                return await race_client.post(
                    f"/inventory/reservations/{reservation_id}/fulfill",
                    json={
                        "quantity": 2,
                        "external_reference": (
                            f"double-fulfill-{iteration}-{token}-{uuid.uuid4().hex}"
                        ),
                    },
                )

            first = asyncio.create_task(fulfill_once("first"))
            second = asyncio.create_task(fulfill_once("second"))
            start.set()
            responses = await asyncio.gather(first, second)
            assert sorted(response.status_code for response in responses) == [200, 409]
            expected_on_hand -= 2
            final = await race_client.get(f"/inventory/reservations/{reservation_id}")
            assert final.json()["status"] == "FULFILLED"
            assert final.json()["fulfilled_quantity"] == 2
            assert final.json()["version"] == 2
            current = await race_client.get(f"/inventory/{inventory_id}")
            assert current.json()["quantity_on_hand"] == expected_on_hand
            assert current.json()["quantity_reserved"] == 0
    finally:
        await cleanup_context(race_client, context)


async def test_adjustment_reservation_oversell_and_negative_balance_matrix(
    race_client: httpx.AsyncClient,
) -> None:
    context = await create_context(race_client, quantity=10)
    product_id = context.product_ids[0]
    warehouse_id = context.warehouse_ids[0]
    try:
        for iteration in range(10):
            start = asyncio.Event()
            issue_task = asyncio.create_task(
                movement(
                    race_client,
                    movement_type="ADJUSTMENT_OUT",
                    product_id=product_id,
                    source_warehouse_id=warehouse_id,
                    quantity=5,
                    external_reference=f"adjust-{iteration}-{uuid.uuid4().hex}",
                    start=start,
                )
            )
            reservation_task = asyncio.create_task(
                reserve(
                    race_client,
                    product_id=product_id,
                    warehouse_id=warehouse_id,
                    quantity=6,
                    external_reference=f"adjust-reserve-{iteration}-{uuid.uuid4().hex}",
                    start=start,
                )
            )
            start.set()
            issue_response, reservation_response = await asyncio.gather(
                issue_task,
                reservation_task,
            )
            assert sorted(
                [issue_response.status_code, reservation_response.status_code]
            ) == [201, 422]

            current = await inventory(
                race_client,
                context,
                warehouse_id,
                product_id,
            )
            assert current["quantity_on_hand"] >= 0
            assert current["quantity_reserved"] <= current["quantity_on_hand"]
            if issue_response.status_code == 201:
                assert current["quantity_on_hand"] == 5
                assert current["quantity_reserved"] == 0
                reversed_response = await race_client.post(
                    f"/inventory/movements/{issue_response.json()['id']}/reverse"
                )
                assert reversed_response.status_code == 201
            else:
                assert current["quantity_on_hand"] == 10
                assert current["quantity_reserved"] == 6
                cancelled = await race_client.post(
                    "/inventory/reservations/"
                    f"{reservation_response.json()['id']}/cancel"
                )
                assert cancelled.status_code == 200
            reset = await inventory(
                race_client,
                context,
                warehouse_id,
                product_id,
            )
            assert reset["quantity_on_hand"] == 10
            assert reset["quantity_reserved"] == 0
            assert reset["quantity_available"] == 10
    finally:
        await cleanup_context(race_client, context)


async def test_idempotent_movement_and_warehouse_deactivation_races(
    race_client: httpx.AsyncClient,
) -> None:
    context = await create_context(race_client, quantity=10)
    product_id = context.product_ids[0]
    warehouse_id = context.warehouse_ids[0]
    expected_on_hand = 10
    try:
        for iteration in range(10):
            external_reference = f"idempotent-{iteration}-{uuid.uuid4().hex}"
            start = asyncio.Event()
            first = asyncio.create_task(
                movement(
                    race_client,
                    movement_type="RECEIPT",
                    product_id=product_id,
                    destination_warehouse_id=warehouse_id,
                    quantity=1,
                    external_reference=external_reference,
                    start=start,
                )
            )
            second = asyncio.create_task(
                movement(
                    race_client,
                    movement_type="RECEIPT",
                    product_id=product_id,
                    destination_warehouse_id=warehouse_id,
                    quantity=1,
                    external_reference=external_reference,
                    start=start,
                )
            )
            start.set()
            responses = await asyncio.gather(first, second)
            assert [response.status_code for response in responses] == [201, 201]
            assert responses[0].json()["id"] == responses[1].json()["id"]
            expected_on_hand += 1
            current = await inventory(
                race_client,
                context,
                warehouse_id,
                product_id,
            )
            assert current["quantity_on_hand"] == expected_on_hand
            movements = await race_client.get(
                "/inventory/movements",
                params={"external_reference": external_reference},
            )
            assert movements.status_code == 200
            assert movements.json()["total"] == 1

            start = asyncio.Event()

            async def deactivate() -> httpx.Response:
                await start.wait()
                return await race_client.delete(f"/warehouses/{warehouse_id}")

            mutation_reference = f"deactivate-{iteration}-{uuid.uuid4().hex}"
            deactivate_task = asyncio.create_task(deactivate())
            mutation_task = asyncio.create_task(
                movement(
                    race_client,
                    movement_type="RECEIPT",
                    product_id=product_id,
                    destination_warehouse_id=warehouse_id,
                    quantity=1,
                    external_reference=mutation_reference,
                    start=start,
                )
            )
            start.set()
            deactivated, mutated = await asyncio.gather(
                deactivate_task,
                mutation_task,
            )
            assert deactivated.status_code == 204
            assert mutated.status_code in {201, 422}
            warehouse = await race_client.get(f"/warehouses/{warehouse_id}")
            assert warehouse.status_code == 200
            assert warehouse.json()["is_active"] is False
            if mutated.status_code == 201:
                expected_on_hand += 1
                reversed_response = await race_client.post(
                    f"/inventory/movements/{mutated.json()['id']}/reverse"
                )
                assert reversed_response.status_code == 422
            reactivated = await race_client.patch(
                f"/warehouses/{warehouse_id}",
                json={"is_active": True},
            )
            assert reactivated.status_code == 200
            if mutated.status_code == 201:
                reversed_response = await race_client.post(
                    f"/inventory/movements/{mutated.json()['id']}/reverse"
                )
                assert reversed_response.status_code == 201
                expected_on_hand -= 1
            current = await inventory(
                race_client,
                context,
                warehouse_id,
                product_id,
            )
            assert current["quantity_on_hand"] == expected_on_hand
    finally:
        await cleanup_context(race_client, context)


async def test_transfer_lock_ordering_and_multi_product_deadlock_matrix(
    race_client: httpx.AsyncClient,
) -> None:
    context = await create_context(
        race_client,
        product_count=2,
        warehouse_count=2,
        quantity=100,
    )
    first_product, second_product = context.product_ids
    first_warehouse, second_warehouse = context.warehouse_ids
    try:
        for iteration in range(10):
            start = asyncio.Event()
            first = asyncio.create_task(
                movement(
                    race_client,
                    movement_type="TRANSFER",
                    product_id=first_product,
                    source_warehouse_id=first_warehouse,
                    destination_warehouse_id=second_warehouse,
                    quantity=1,
                    external_reference=f"transfer-a-{iteration}-{uuid.uuid4().hex}",
                    start=start,
                )
            )
            second = asyncio.create_task(
                movement(
                    race_client,
                    movement_type="TRANSFER",
                    product_id=second_product,
                    source_warehouse_id=second_warehouse,
                    destination_warehouse_id=first_warehouse,
                    quantity=1,
                    external_reference=f"transfer-b-{iteration}-{uuid.uuid4().hex}",
                    start=start,
                )
            )
            start.set()
            responses = await asyncio.wait_for(
                asyncio.gather(first, second),
                timeout=10,
            )
            assert [response.status_code for response in responses] == [201, 201]
            assert (
                await inventory(
                    race_client,
                    context,
                    first_warehouse,
                    first_product,
                )
            )["quantity_on_hand"] == 99
            assert (
                await inventory(
                    race_client,
                    context,
                    second_warehouse,
                    first_product,
                )
            )["quantity_on_hand"] == 101
            assert (
                await inventory(
                    race_client,
                    context,
                    second_warehouse,
                    second_product,
                )
            )["quantity_on_hand"] == 99
            assert (
                await inventory(
                    race_client,
                    context,
                    first_warehouse,
                    second_product,
                )
            )["quantity_on_hand"] == 101

            for response in responses:
                reversed_response = await race_client.post(
                    f"/inventory/movements/{response.json()['id']}/reverse"
                )
                assert reversed_response.status_code == 201
            for product_id in context.product_ids:
                for warehouse_id in context.warehouse_ids:
                    assert (
                        await inventory(
                            race_client,
                            context,
                            warehouse_id,
                            product_id,
                        )
                    )["quantity_on_hand"] == 100
    finally:
        await cleanup_context(race_client, context)
