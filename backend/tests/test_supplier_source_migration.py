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

PREVIOUS_HEAD = "e9f0a1b2c3d4"
SOURCE_HEAD = "f0a1b2c3d4e5"


async def source_contract(
    database: str,
) -> tuple[int, int, set[str], set[str], str]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        sequence = await connection.fetchval(
            "SELECT count(*) FROM pg_class WHERE relkind='S' "
            "AND relname='supplier_source_code_seq'"
        )
        length = await connection.fetchval(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name='supplier_sources' AND column_name='source_code'"
        )
        constraints = {
            row["conname"]
            for row in await connection.fetch(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid='supplier_sources'::regclass"
            )
        }
        indexes = {
            row["indexname"]
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes WHERE tablename='supplier_sources'"
            )
        }
        foreign_key = await connection.fetchval(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname='fk_supplier_sources_supplier_id_suppliers'"
        )
        return int(sequence), int(length), constraints, indexes, str(foreign_key)
    finally:
        await connection.close()


async def source_table_exists(database: str) -> bool:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        return bool(
            await connection.fetchval(
                "SELECT to_regclass('public.supplier_sources') IS NOT NULL"
            )
        )
    finally:
        await connection.close()


def test_supplier_source_migration_round_trip_and_contract() -> None:
    database = f"supplier_source_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", SOURCE_HEAD)
        sequence, length, constraints, indexes, foreign_key = asyncio.run(
            source_contract(database)
        )
        assert sequence == 1
        assert length == 50
        assert {
            "ck_supplier_sources_source_type_valid",
            "ck_supplier_sources_status_valid",
            "ck_supplier_sources_validation_status_valid",
            "fk_supplier_sources_supplier_id_suppliers",
            "uq_supplier_sources_source_code",
        } <= constraints
        assert {
            "uq_supplier_sources_active_supplier_name",
            "ix_supplier_sources_supplier_active",
            "ix_supplier_sources_supplier_type_status",
        } <= indexes
        assert "ON DELETE RESTRICT" in foreign_key

        _alembic(database, "downgrade", PREVIOUS_HEAD)
        assert not asyncio.run(source_table_exists(database))

        _alembic(database, "upgrade", SOURCE_HEAD)
        assert asyncio.run(source_table_exists(database))
    finally:
        asyncio.run(_drop_database(database))
