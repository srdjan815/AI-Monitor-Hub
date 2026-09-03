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

PREVIOUS_HEAD = "f0a1b2c3d4e5"
SCHEMA_HEAD = "a1b2c3d4e5f6"


async def contract(database: str) -> tuple[int, int, set[str], set[str]]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        sequence = await connection.fetchval(
            "SELECT count(*) FROM pg_class WHERE relkind='S' "
            "AND relname='supplier_schema_code_seq'"
        )
        length = await connection.fetchval(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name='supplier_schema_profiles' AND column_name='schema_code'"
        )
        constraints = {
            row["conname"]
            for row in await connection.fetch(
                "SELECT conname FROM pg_constraint WHERE conrelid IN "
                "('supplier_schema_profiles'::regclass,"
                "'supplier_schema_fields'::regclass)"
            )
        }
        indexes = {
            row["indexname"]
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes WHERE tablename IN "
                "('supplier_schema_profiles','supplier_schema_fields')"
            )
        }
        return int(sequence), int(length), constraints, indexes
    finally:
        await connection.close()


async def tables_exist(database: str) -> bool:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        return bool(
            await connection.fetchval(
                "SELECT to_regclass('public.supplier_schema_profiles') IS NOT NULL "
                "OR to_regclass('public.supplier_schema_fields') IS NOT NULL"
            )
        )
    finally:
        await connection.close()


def test_supplier_schema_migration_round_trip_and_contract() -> None:
    database = f"supplier_schema_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", SCHEMA_HEAD)
        sequence, length, constraints, indexes = asyncio.run(contract(database))
        assert sequence == 1
        assert length == 50
        assert {
            "ck_supplier_schema_profiles_status_valid",
            "ck_supplier_schema_fields_data_type_valid",
        } <= constraints
        assert any(
            name.startswith("fk_supplier_schema_profiles_source_connection_id_")
            for name in constraints
        )
        assert any(
            name.startswith("fk_supplier_schema_fields_schema_profile_id_")
            for name in constraints
        )
        assert {
            "uq_supplier_schema_profiles_active_source",
            "uq_supplier_schema_fields_active_code",
            "uq_supplier_schema_fields_active_position",
            "uq_supplier_schema_fields_active_key",
            "uq_supplier_schema_fields_active_price",
        } <= indexes

        _alembic(database, "downgrade", PREVIOUS_HEAD)
        assert not asyncio.run(tables_exist(database))
        _alembic(database, "upgrade", SCHEMA_HEAD)
        assert asyncio.run(tables_exist(database))
    finally:
        asyncio.run(_drop_database(database))
