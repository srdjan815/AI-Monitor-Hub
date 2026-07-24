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

PREVIOUS_HEAD = "a1b2c3d4e5f6"
MAPPING_HEAD = "a2b3c4d5e6f7"


async def contract(database: str) -> tuple[int, int, str, str, set[str]]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        sequence = await connection.fetchval(
            "SELECT count(*) FROM pg_class WHERE relkind='S' "
            "AND relname='supplier_mapping_code_seq'"
        )
        length = await connection.fetchval(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name='supplier_mapping_profiles' "
            "AND column_name='mapping_code'"
        )
        default_type = await connection.fetchval(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='supplier_mapping_rules' "
            "AND column_name='default_value'"
        )
        validation_type = await connection.fetchval(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name='supplier_mapping_rules' "
            "AND column_name='validation_rule'"
        )
        indexes = {
            row["indexname"]
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes WHERE tablename IN "
                "('supplier_mapping_profiles','supplier_mapping_rules')"
            )
        }
        return (
            int(sequence),
            int(length),
            str(default_type),
            str(validation_type),
            indexes,
        )
    finally:
        await connection.close()


async def tables_exist(database: str) -> bool:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        return bool(
            await connection.fetchval(
                "SELECT to_regclass('public.supplier_mapping_profiles') IS NOT NULL "
                "OR to_regclass('public.supplier_mapping_rules') IS NOT NULL"
            )
        )
    finally:
        await connection.close()


def test_supplier_mapping_migration_round_trip_and_contract() -> None:
    database = f"supplier_mapping_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", MAPPING_HEAD)
        sequence, length, default_type, validation_type, indexes = asyncio.run(
            contract(database)
        )
        assert sequence == 1
        assert length == 50
        assert default_type == "text"
        assert validation_type == "text"
        assert {
            "uq_supplier_mapping_profiles_active_schema",
            "uq_supplier_mapping_rules_active_field",
            "uq_supplier_mapping_rules_active_target",
            "uq_supplier_mapping_rules_active_priority",
        } <= indexes
        _alembic(database, "downgrade", PREVIOUS_HEAD)
        assert not asyncio.run(tables_exist(database))
        _alembic(database, "upgrade", MAPPING_HEAD)
        assert asyncio.run(tables_exist(database))
    finally:
        asyncio.run(_drop_database(database))
