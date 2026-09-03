from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.modules.catalog.models import Category, Product


API_ROOT = "http://localhost:8000/api/v1"


async def _concurrent_product_write(
    product_id: uuid.UUID,
    name: str,
    ready: asyncio.Event,
    start: asyncio.Event,
) -> str:
    async with AsyncSessionLocal() as session:
        product = await session.get(Product, product_id)
        assert product is not None
        ready.set()
        await start.wait()
        product.name = name
        product.version += 1
        try:
            await session.commit()
        except StaleDataError:
            await session.rollback()
            return "stale"
        return "committed"


@pytest.mark.asyncio
async def test_product_mapper_prevents_lost_updates_repeatedly() -> None:
    suffix = uuid.uuid4().hex
    async with AsyncSessionLocal() as session:
        category = Category(
            name=f"Concurrency category {suffix}",
            code=f"concurrency_category_{suffix}",
        )
        session.add(category)
        await session.flush()
        product = Product(
            category_id=category.id,
            name=f"Concurrency product {suffix}",
            code=f"concurrency_product_{suffix}",
        )
        session.add(product)
        await session.commit()
        product_id = product.id
        category_id = category.id

    try:
        for iteration in range(10):
            first_ready = asyncio.Event()
            second_ready = asyncio.Event()
            start = asyncio.Event()
            first = asyncio.create_task(
                _concurrent_product_write(
                    product_id,
                    f"first-{iteration}-{suffix}",
                    first_ready,
                    start,
                )
            )
            second = asyncio.create_task(
                _concurrent_product_write(
                    product_id,
                    f"second-{iteration}-{suffix}",
                    second_ready,
                    start,
                )
            )
            await asyncio.gather(first_ready.wait(), second_ready.wait())
            start.set()
            outcomes = await asyncio.gather(first, second)
            assert sorted(outcomes) == ["committed", "stale"]

            async with AsyncSessionLocal() as verification:
                current = await verification.get(Product, product_id)
                assert current is not None
                assert current.version == iteration + 2
                assert current.name in {
                    f"first-{iteration}-{suffix}",
                    f"second-{iteration}-{suffix}",
                }
    finally:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(Product).where(Product.id == product_id))
            await cleanup.execute(delete(Category).where(Category.id == category_id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_product_update_deactivate_and_restore_uniqueness_races_repeatably() -> (
    None
):
    suffix = uuid.uuid4().hex
    async with AsyncSessionLocal() as session:
        category_row = Category(
            name=f"Product race category {suffix}",
            code=f"product_race_category_{suffix}",
        )
        session.add(category_row)
        await session.commit()
        category_id = category_row.id

    product_ids: list[uuid.UUID] = []
    try:
        for iteration in range(10):
            async with AsyncSessionLocal() as session:
                row = Product(
                    category_id=category_id,
                    name=f"Product race {iteration} {suffix}",
                    code=f"product_race_{iteration}_{suffix}",
                )
                session.add(row)
                await session.commit()
                product_id = row.id
                product_ids.append(product_id)

            first_ready = asyncio.Event()
            second_ready = asyncio.Event()
            start = asyncio.Event()

            async def update() -> str:
                async with AsyncSessionLocal() as session:
                    entity = await session.get(Product, product_id)
                    assert entity is not None
                    first_ready.set()
                    await start.wait()
                    entity.name = f"updated-{iteration}-{suffix}"
                    entity.version += 1
                    try:
                        await session.commit()
                    except StaleDataError:
                        await session.rollback()
                        assert await session.scalar(select(1)) == 1
                        return "stale"
                    return "updated"

            async def deactivate() -> str:
                async with AsyncSessionLocal() as session:
                    entity = await session.get(Product, product_id)
                    assert entity is not None
                    second_ready.set()
                    await start.wait()
                    entity.is_active = False
                    entity.version += 1
                    try:
                        await session.commit()
                    except StaleDataError:
                        await session.rollback()
                        assert await session.scalar(select(1)) == 1
                        return "stale"
                    return "deactivated"

            update_task = asyncio.create_task(update())
            deactivate_task = asyncio.create_task(deactivate())
            await asyncio.gather(first_ready.wait(), second_ready.wait())
            start.set()
            outcomes = await asyncio.gather(update_task, deactivate_task)
            assert outcomes.count("stale") == 1
            assert set(outcomes) & {"updated", "deactivated"}

            async with AsyncSessionLocal() as verification:
                current = await verification.get(Product, product_id)
                assert current is not None
                assert current.version == 2
                assert (
                    current.name == f"updated-{iteration}-{suffix}"
                    or current.is_active is False
                )

            async with AsyncSessionLocal() as session:
                inactive = await session.get(Product, product_id)
                assert inactive is not None
                inactive.is_active = False
                inactive.version += 1
                await session.commit()

            restore_ready = asyncio.Event()
            duplicate_ready = asyncio.Event()
            restore_start = asyncio.Event()

            async def restore() -> str:
                async with AsyncSessionLocal() as session:
                    entity = await session.get(Product, product_id)
                    assert entity is not None
                    restore_ready.set()
                    await restore_start.wait()
                    entity.is_active = True
                    entity.version += 1
                    await session.commit()
                    return "restored"

            async def duplicate() -> str:
                async with AsyncSessionLocal() as session:
                    session.add(
                        Product(
                            category_id=category_id,
                            name=f"Duplicate race {iteration} {suffix}",
                            code=f"product_race_{iteration}_{suffix}",
                        )
                    )
                    duplicate_ready.set()
                    await restore_start.wait()
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
                        assert await session.scalar(select(1)) == 1
                        return "unique_conflict"
                    return "unexpected_commit"

            restore_task = asyncio.create_task(restore())
            duplicate_task = asyncio.create_task(duplicate())
            await asyncio.gather(restore_ready.wait(), duplicate_ready.wait())
            restore_start.set()
            restore_outcomes = await asyncio.gather(restore_task, duplicate_task)
            assert sorted(restore_outcomes) == ["restored", "unique_conflict"]

            async with AsyncSessionLocal() as verification:
                restored = await verification.get(Product, product_id)
                assert restored is not None
                assert restored.is_active is True
                duplicates = await verification.scalar(
                    select(Product)
                    .where(Product.code == f"product_race_{iteration}_{suffix}")
                    .with_only_columns(Product.id)
                )
                assert duplicates == product_id
    finally:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(Product).where(Product.id.in_(product_ids)))
            await cleanup.execute(delete(Category).where(Category.id == category_id))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_category_move_and_reorder_conflicts_are_optimistically_fenced() -> None:
    suffix = uuid.uuid4().hex
    category_ids: list[uuid.UUID] = []
    try:
        for iteration in range(10):
            async with AsyncSessionLocal() as session:
                first_parent = Category(
                    name=f"First parent {iteration} {suffix}",
                    code=f"first_parent_{iteration}_{suffix}",
                )
                second_parent = Category(
                    name=f"Second parent {iteration} {suffix}",
                    code=f"second_parent_{iteration}_{suffix}",
                )
                child = Category(
                    name=f"Child {iteration} {suffix}",
                    code=f"child_{iteration}_{suffix}",
                    parent=first_parent,
                    position=0,
                )
                session.add_all([first_parent, second_parent, child])
                await session.commit()
                category_ids.extend([first_parent.id, second_parent.id, child.id])
                child_id = child.id
                second_parent_id = second_parent.id

            move_ready = asyncio.Event()
            reorder_ready = asyncio.Event()
            start = asyncio.Event()

            async def move() -> str:
                async with AsyncSessionLocal() as session:
                    entity = await session.get(Category, child_id)
                    assert entity is not None
                    move_ready.set()
                    await start.wait()
                    entity.parent_id = second_parent_id
                    entity.version += 1
                    try:
                        await session.commit()
                    except StaleDataError:
                        await session.rollback()
                        assert await session.scalar(select(1)) == 1
                        return "stale"
                    return "moved"

            async def reorder() -> str:
                async with AsyncSessionLocal() as session:
                    entity = await session.get(Category, child_id)
                    assert entity is not None
                    reorder_ready.set()
                    await start.wait()
                    entity.position = iteration + 1
                    entity.version += 1
                    try:
                        await session.commit()
                    except StaleDataError:
                        await session.rollback()
                        assert await session.scalar(select(1)) == 1
                        return "stale"
                    return "reordered"

            move_task = asyncio.create_task(move())
            reorder_task = asyncio.create_task(reorder())
            await asyncio.gather(move_ready.wait(), reorder_ready.wait())
            start.set()
            outcomes = await asyncio.gather(move_task, reorder_task)
            assert outcomes.count("stale") == 1
            assert set(outcomes) & {"moved", "reordered"}

            async with AsyncSessionLocal() as verification:
                current = await verification.get(Category, child_id)
                assert current is not None
                assert current.version == 2
                assert (
                    current.parent_id == second_parent_id
                    or current.position == iteration + 1
                )
    finally:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(Category).where(Category.id.in_(category_ids)))
            await cleanup.commit()


@pytest.mark.asyncio
async def test_concurrent_reservations_cannot_oversell() -> None:
    suffix = uuid.uuid4().hex
    headers = {"Authorization": f"Bearer {create_access_token('concurrency-test')}"}
    async with httpx.AsyncClient(
        base_url=API_ROOT,
        timeout=30.0,
        headers=headers,
    ) as client:
        category = await client.post(
            "/categories",
            json={
                "name": f"Oversell category {suffix}",
                "code": f"oversell_category_{suffix}",
            },
        )
        assert category.status_code == 201, category.text
        category_id = category.json()["id"]
        product = await client.post(
            "/products",
            json={
                "category_id": category_id,
                "name": f"Oversell product {suffix}",
                "code": f"oversell_product_{suffix}",
            },
        )
        assert product.status_code == 201, product.text
        product_id = product.json()["id"]
        warehouse = await client.post(
            "/warehouses",
            json={
                "name": f"Oversell warehouse {suffix}",
                "code": f"oversell_warehouse_{suffix}",
            },
        )
        assert warehouse.status_code == 201, warehouse.text
        warehouse_id = warehouse.json()["id"]
        inventory = await client.post(
            "/inventory",
            json={
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity_on_hand": 10,
            },
        )
        assert inventory.status_code == 201, inventory.text
        inventory_id = inventory.json()["id"]

        for iteration in range(10):
            start = asyncio.Event()

            async def reserve(token: str) -> httpx.Response:
                await start.wait()
                return await client.post(
                    "/inventory/reservations",
                    json={
                        "warehouse_id": warehouse_id,
                        "product_id": product_id,
                        "quantity": 6,
                        "external_reference": (
                            f"oversell-{iteration}-{token}-{suffix}"
                        ),
                    },
                )

            first = asyncio.create_task(reserve("first"))
            second = asyncio.create_task(reserve("second"))
            start.set()
            responses = await asyncio.gather(first, second)
            assert sorted(response.status_code for response in responses) == [
                201,
                422,
            ]
            successful = next(
                response.json() for response in responses if response.status_code == 201
            )
            balance = await client.get(f"/inventory/{inventory_id}")
            assert balance.status_code == 200
            assert balance.json()["quantity_reserved"] == 6
            assert balance.json()["quantity_available"] == 4

            cancelled = await client.post(
                f"/inventory/reservations/{successful['id']}/cancel"
            )
            assert cancelled.status_code == 200
            balance = await client.get(f"/inventory/{inventory_id}")
            assert balance.json()["quantity_reserved"] == 0
            assert balance.json()["quantity_available"] == 10

        await client.delete(f"/inventory/{inventory_id}")
        await client.delete(f"/warehouses/{warehouse_id}")
        await client.delete(f"/products/{product_id}")
        await client.delete(f"/categories/{category_id}")
