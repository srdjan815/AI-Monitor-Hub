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

PREVIOUS = "c9d0e1f2a3b4"
HEAD = "d0e1f2a3b4c5"


async def _contract(database: str) -> tuple[set[str], tuple[str, str]]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        tables = {
            row["tablename"]
            for row in await connection.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('monitor_currency_settings','supplier_currency_settings','supplier_exchange_rates','supplier_currency_events')"
            )
        }
        monitor = await connection.fetchrow(
            "SELECT currency_code, rate_to_rsd::text FROM monitor_currency_settings"
        )
        return tables, (monitor["currency_code"], monitor["rate_to_rsd"])
    finally:
        await connection.close()


async def _absent(database: str) -> bool:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        return not bool(
            await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='supplier_currency_settings')"
            )
        )
    finally:
        await connection.close()


def test_supplier_currency_migration_round_trip() -> None:
    database = f"supplier_currency_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", HEAD)
        tables, monitor = asyncio.run(_contract(database))
        assert tables == {
            "monitor_currency_settings",
            "supplier_currency_settings",
            "supplier_exchange_rates",
            "supplier_currency_events",
        }
        assert monitor == ("RSD", "1.00000000")
        _alembic(database, "downgrade", PREVIOUS)
        assert asyncio.run(_absent(database))
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_contract(database))[1] == monitor
    finally:
        asyncio.run(_drop_database(database))
