from __future__ import annotations

import asyncio
import uuid

import asyncpg

from tests.test_supplier_migration import (
    _alembic,
    _create_database,
    _drop_database,
    _postgres_url,
)

PREVIOUS = "a7b8c9d0e1f2"
HEAD = "a8c9d0e1f2a3"


async def _table_exists(database: str) -> bool:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        return bool(
            await connection.fetchval(
                "SELECT to_regclass('public.system_cleanup_audit') IS NOT NULL"
            )
        )
    finally:
        await connection.close()


def test_system_resource_migration_round_trip() -> None:
    database = f"system_resource_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_table_exists(database))
        _alembic(database, "downgrade", PREVIOUS)
        assert not asyncio.run(_table_exists(database))
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_table_exists(database))
    finally:
        asyncio.run(_drop_database(database))
