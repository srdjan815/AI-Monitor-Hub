from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.modules.catalog.models import Category


DATABASE_URL = os.getenv(
    "PRODUCT_CONTENT_INTEGRATION_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@db:5432/ai_content_integration",
)


def session_factory(*, serializable: bool = False) -> tuple:
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=6,
        isolation_level="SERIALIZABLE" if serializable else "READ COMMITTED",
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_deadlock_loser_rolls_back_and_session_remains_usable() -> None:
    engine, sessions = session_factory()
    suffix = uuid.uuid4().hex
    async with sessions() as session:
        first = Category(name=f"Deadlock first {suffix}", code=f"deadlock_a_{suffix}")
        second = Category(
            name=f"Deadlock second {suffix}",
            code=f"deadlock_b_{suffix}",
        )
        session.add_all([first, second])
        await session.commit()
        first_id = first.id
        second_id = second.id

    first_ready = asyncio.Event()
    second_ready = asyncio.Event()
    start = asyncio.Event()

    async def lock_in_order(
        first_lock: uuid.UUID,
        second_lock: uuid.UUID,
        ready: asyncio.Event,
    ) -> str:
        async with sessions() as session:
            await session.execute(
                select(Category).where(Category.id == first_lock).with_for_update()
            )
            ready.set()
            await start.wait()
            try:
                await session.execute(
                    select(Category).where(Category.id == second_lock).with_for_update()
                )
                await session.commit()
                return "committed"
            except DBAPIError:
                await session.rollback()
                assert await session.scalar(select(1)) == 1
                return "deadlock"

    first_task = asyncio.create_task(lock_in_order(first_id, second_id, first_ready))
    second_task = asyncio.create_task(lock_in_order(second_id, first_id, second_ready))
    await asyncio.gather(first_ready.wait(), second_ready.wait())
    start.set()
    outcomes = await asyncio.gather(first_task, second_task)
    assert sorted(outcomes) == ["committed", "deadlock"]

    async with sessions() as session:
        rows = list(
            (
                await session.scalars(
                    select(Category).where(Category.id.in_([first_id, second_id]))
                )
            ).all()
        )
        assert {row.name for row in rows} == {
            f"Deadlock first {suffix}",
            f"Deadlock second {suffix}",
        }
        for row in rows:
            await session.delete(row)
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_lock_timeout_has_no_partial_mutation_or_leaked_transaction() -> None:
    engine, sessions = session_factory()
    suffix = uuid.uuid4().hex
    async with sessions() as setup:
        entity = Category(
            name=f"Lock timeout {suffix}",
            code=f"lock_timeout_{suffix}",
        )
        setup.add(entity)
        await setup.commit()
        entity_id = entity.id

    async with sessions() as holder, sessions() as contender:
        await holder.execute(
            select(Category).where(Category.id == entity_id).with_for_update()
        )
        await contender.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(DBAPIError):
            await contender.execute(
                select(Category).where(Category.id == entity_id).with_for_update()
            )
        await contender.rollback()
        assert await contender.scalar(select(1)) == 1
        await holder.rollback()

    async with sessions() as verification:
        current = await verification.get(Category, entity_id)
        assert current is not None
        assert current.name == f"Lock timeout {suffix}"
        await verification.delete(current)
        await verification.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_serialization_failure_preserves_one_atomic_winner() -> None:
    engine, sessions = session_factory(serializable=True)
    suffix = uuid.uuid4().hex
    async with sessions() as setup:
        entity = Category(
            name=f"Serialization {suffix}",
            code=f"serialization_{suffix}",
        )
        setup.add(entity)
        await setup.commit()
        entity_id = entity.id

    first_ready = asyncio.Event()
    second_ready = asyncio.Event()
    start = asyncio.Event()

    async def mutate(label: str, ready: asyncio.Event) -> str:
        async with sessions() as session:
            current = await session.get(Category, entity_id)
            assert current is not None
            ready.set()
            await start.wait()
            try:
                await session.execute(
                    update(Category)
                    .where(Category.id == entity_id)
                    .values(name=f"{label} {suffix}")
                )
                await session.commit()
                return label
            except DBAPIError:
                await session.rollback()
                assert await session.scalar(select(1)) == 1
                return "serialization"

    first_task = asyncio.create_task(mutate("first", first_ready))
    second_task = asyncio.create_task(mutate("second", second_ready))
    await asyncio.gather(first_ready.wait(), second_ready.wait())
    start.set()
    outcomes = await asyncio.gather(first_task, second_task)
    assert outcomes.count("serialization") == 1
    assert set(outcomes) & {"first", "second"}

    async with sessions() as verification:
        current = await verification.get(Category, entity_id)
        assert current is not None
        assert current.name in {f"first {suffix}", f"second {suffix}"}
        await verification.delete(current)
        await verification.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_connection_termination_rolls_back_uncommitted_flush() -> None:
    engine, sessions = session_factory()
    suffix = uuid.uuid4().hex
    victim = sessions()
    try:
        backend_pid = int(await victim.scalar(text("SELECT pg_backend_pid()")))
        victim.add(
            Category(
                name=f"Terminated connection {suffix}",
                code=f"terminated_connection_{suffix}",
            )
        )
        await victim.flush()

        async with sessions() as killer:
            terminated = await killer.scalar(
                text("SELECT pg_terminate_backend(:backend_pid)"),
                {"backend_pid": backend_pid},
            )
            assert terminated is True

        with pytest.raises(DBAPIError):
            await victim.commit()
        await victim.rollback()
        assert await victim.scalar(select(1)) == 1
    finally:
        await victim.close()

    async with sessions() as verification:
        persisted = await verification.scalar(
            select(Category).where(Category.code == f"terminated_connection_{suffix}")
        )
        assert persisted is None
    await engine.dispose()
