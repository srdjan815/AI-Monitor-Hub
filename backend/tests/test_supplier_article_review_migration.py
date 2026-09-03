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

PREVIOUS = "b8c4bdfd5754"
HEAD = "c9d0e1f2a3b4"


async def _contract(database: str) -> tuple[set[str], set[str]]:
    connection = await asyncpg.connect(_postgres_url(database))
    try:
        tables = {
            row["tablename"]
            for row in await connection.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND tablename LIKE 'supplier_article_review%'"
            )
        }
        indexes = {
            row["indexname"]
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
                "AND tablename IN ('supplier_article_reviews', "
                "'supplier_article_review_events')"
            )
        }
        return tables, indexes
    finally:
        await connection.close()


def test_article_review_migration_round_trip() -> None:
    database = f"article_review_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", HEAD)
        tables, indexes = asyncio.run(_contract(database))
        assert tables == {
            "supplier_article_reviews",
            "supplier_article_review_events",
        }
        assert {
            "ix_article_reviews_queue",
            "ix_article_reviews_issue_codes",
            "ix_article_review_events_review_created",
        } <= indexes
        _alembic(database, "downgrade", PREVIOUS)
        assert asyncio.run(_contract(database)) == (set(), set())
        _alembic(database, "upgrade", HEAD)
        assert asyncio.run(_contract(database))[0] == tables
    finally:
        asyncio.run(_drop_database(database))
