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

PREVIOUS = "a8c9d0e1f2a3"
HEAD = "a9d0e1f2a3b4"


async def _state(database: str) -> tuple[bool, bool, bool]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        settings = bool(
            await connection.fetchval(
                "SELECT to_regclass('public.artifact_archive_settings') IS NOT NULL"
            )
        )
        transfers = bool(
            await connection.fetchval(
                "SELECT to_regclass('public.artifact_archive_transfers') IS NOT NULL"
            )
        )
        unique_reference = bool(
            await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_supplier_source_artifacts_storage_reference')"
            )
        )
        return settings, transfers, unique_reference
    finally:
        await connection.close()


def test_artifact_archive_migration_round_trip() -> None:
    database = f"artifact_archive_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_state(database)) == (True, True, True)
        _alembic(database, "downgrade", PREVIOUS)
        assert asyncio.run(_state(database)) == (False, False, True)
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_state(database)) == (True, True, True)
    finally:
        asyncio.run(_drop_database(database))
