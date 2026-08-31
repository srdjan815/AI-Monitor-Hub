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

PREVIOUS = "a6b7c8d9e0f1"
HEAD = "b8c4bdfd5754"
TABLES = {
    "supplier_schema_compatibility_reports",
    "supplier_source_artifacts",
    "supplier_source_pipeline_runs",
    "supplier_source_schedules",
}


async def _contract(database: str) -> tuple[set[str], set[str], set[str]]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        tables = {
            row["tablename"]
            for row in await connection.fetch(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename = ANY($1::text[])",
                list(TABLES),
            )
        }
        indexes = {
            row["indexname"]
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname='public' AND tablename = "
                "'supplier_source_pipeline_runs'"
            )
        }
        sequences = {
            row["relname"]
            for row in await connection.fetch(
                "SELECT relname FROM pg_class WHERE relkind='S' "
                "AND relname LIKE 'supplier_source_%_code_seq'"
            )
        }
        return tables, indexes, sequences
    finally:
        await connection.close()


def test_supplier_pipeline_migration_round_trip_and_contract() -> None:
    database = f"supplier_pipeline_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", HEAD)
        tables, indexes, sequences = asyncio.run(_contract(database))
        assert tables == TABLES
        assert {
            "uq_supplier_source_pipeline_runs_source_active",
            "uq_supplier_source_pipeline_runs_schedule_occurrence",
        } <= indexes
        assert {
            "supplier_source_artifact_code_seq",
            "supplier_source_pipeline_code_seq",
        } <= sequences

        _alembic(database, "downgrade", PREVIOUS)
        assert asyncio.run(_contract(database)) == (set(), set(), set())

        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_contract(database))[0] == TABLES
    finally:
        asyncio.run(_drop_database(database))
