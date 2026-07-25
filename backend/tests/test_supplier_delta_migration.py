from __future__ import annotations

import asyncio
import uuid

import asyncpg

from tests.test_supplier_migration import _alembic, _create_database, _drop_database, _postgres_url

PREVIOUS = "a4b5c6d7e8f9"
HEAD = "a5b6c7d8e9f1"


async def _contract(database: str) -> tuple[set[str], bool]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        tables = {row["tablename"] for row in await connection.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'supplier_delta%'")}
        sequence = bool(await connection.fetchval("SELECT to_regclass('public.supplier_delta_code_seq') IS NOT NULL"))
        return tables, sequence
    finally:
        await connection.close()


def test_supplier_delta_migration_round_trip() -> None:
    database = f"supplier_delta_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", HEAD)
        tables, sequence = asyncio.run(_contract(database))
        assert tables == {"supplier_delta_runs", "supplier_delta_items", "supplier_delta_field_changes"}
        assert sequence
        _alembic(database, "downgrade", PREVIOUS)
        assert asyncio.run(_contract(database)) == (set(), False)
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_contract(database))[1]
    finally:
        asyncio.run(_drop_database(database))
