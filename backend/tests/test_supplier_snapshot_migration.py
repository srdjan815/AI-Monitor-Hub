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

PREVIOUS_HEAD = "a3b4c5d6e7f8"
SNAPSHOT_HEAD = "a4b5c6d7e8f9"


async def contract(database: str) -> tuple[int, set[str], set[str]]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        sequence = await connection.fetchval(
            "SELECT count(*) FROM pg_class WHERE relkind='S' "
            "AND relname='supplier_snapshot_code_seq'"
        )
        tables = {
            row["tablename"]
            for row in await connection.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename LIKE 'supplier_snapshot%'"
            )
        }
        indexes = {
            row["indexname"]
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes WHERE tablename IN "
                "('supplier_snapshots','supplier_snapshot_items',"
                "'supplier_snapshot_archive_operations')"
            )
        }
        return int(sequence), tables, indexes
    finally:
        await connection.close()


async def tables_exist(database: str) -> bool:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        return bool(
            await connection.fetchval(
                "SELECT to_regclass('public.supplier_snapshots') IS NOT NULL "
                "OR to_regclass('public.supplier_snapshot_items') IS NOT NULL "
                "OR to_regclass("
                "'public.supplier_snapshot_archive_operations') IS NOT NULL"
            )
        )
    finally:
        await connection.close()


def test_supplier_snapshot_migration_round_trip_and_contract() -> None:
    database = f"supplier_snapshot_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", SNAPSHOT_HEAD)
        sequence, tables, indexes = asyncio.run(contract(database))
        assert sequence == 1
        assert {
            "supplier_snapshots",
            "supplier_snapshot_items",
            "supplier_snapshot_archive_operations",
        } <= tables
        assert {
            "uq_supplier_snapshots_acquisition_run_id",
            "ix_supplier_snapshots_source_state_created",
            "uq_supplier_snapshot_items_staged_record",
            "ix_supplier_snapshot_archive_operations_snapshot_created",
        } <= indexes
        _alembic(database, "downgrade", PREVIOUS_HEAD)
        assert not asyncio.run(tables_exist(database))
        _alembic(database, "upgrade", SNAPSHOT_HEAD)
        assert asyncio.run(tables_exist(database))
    finally:
        asyncio.run(_drop_database(database))
