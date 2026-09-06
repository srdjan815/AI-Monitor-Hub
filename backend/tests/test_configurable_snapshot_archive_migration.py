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

PREVIOUS = "b0e1f2a3b4c5"
HEAD = "c1f2a3b4c5d6"


async def _snapshot_path_column(database: str) -> tuple[bool, str | None]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        row = await connection.fetchrow("""
            SELECT is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'artifact_archive_settings'
              AND column_name = 'snapshot_relative_path'
            """)
        return (row is not None, None if row is None else row["is_nullable"])
    finally:
        await connection.close()


def test_configurable_snapshot_archive_migration_round_trip() -> None:
    database = f"snapshot_archive_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_snapshot_path_column(database)) == (True, "NO")
        _alembic(database, "downgrade", PREVIOUS)
        assert asyncio.run(_snapshot_path_column(database)) == (False, None)
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_snapshot_path_column(database)) == (True, "NO")
    finally:
        asyncio.run(_drop_database(database))
