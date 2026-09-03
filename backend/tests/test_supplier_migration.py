from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

from app.core.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_HEAD = "c7d8e9f0a1b2"
SUPPLIER_HEAD = "e9f0a1b2c3d4"


def _postgres_url(database: str) -> str:
    return str(
        make_url(settings.database_url)
        .set(drivername="postgresql", database=database)
        .render_as_string(hide_password=False)
    )


async def _create_database(name: str) -> None:
    connection = await asyncpg.connect(_postgres_url("postgres"))
    try:
        await connection.execute(f'CREATE DATABASE "{name}"')
    finally:
        await connection.close()


async def _drop_database(name: str) -> None:
    connection = await asyncpg.connect(_postgres_url("postgres"))
    try:
        await connection.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = $1 AND pid <> pg_backend_pid()",
            name,
        )
        await connection.execute(f'DROP DATABASE IF EXISTS "{name}"')
    finally:
        await connection.close()


async def _supplier_contract(name: str) -> tuple[str, set[str], set[str]]:
    connection = await asyncpg.connect(_postgres_url(name))
    try:
        length = await connection.fetchval(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='suppliers' "
            "AND column_name='supplier_code'"
        )
        constraints = {
            row["conname"]
            for row in await connection.fetch(
                "SELECT conname FROM pg_constraint WHERE conrelid IN "
                "('suppliers'::regclass, 'supplier_contacts'::regclass)"
            )
        }
        indexes = {
            row["indexname"]
            for row in await connection.fetch(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public' "
                "AND tablename IN ('suppliers','supplier_contacts')"
            )
        }
        return str(length), constraints, indexes
    finally:
        await connection.close()


async def _supplier_tables_exist(name: str) -> bool:
    connection = await asyncpg.connect(_postgres_url(name))
    try:
        return bool(
            await connection.fetchval(
                "SELECT to_regclass('public.suppliers') IS NOT NULL "
                "OR to_regclass('public.supplier_contacts') IS NOT NULL"
            )
        )
    finally:
        await connection.close()


def _alembic(database: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        make_url(settings.database_url)
        .set(database=database)
        .render_as_string(hide_password=False)
    )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_supplier_migration_upgrade_downgrade_reupgrade_contract() -> None:
    database = f"supplier_migration_{uuid.uuid4().hex}"
    asyncio.run(_create_database(database))
    try:
        _alembic(database, "upgrade", "head")
        length, constraints, indexes = asyncio.run(_supplier_contract(database))
        assert length == "50"
        assert {
            "ck_suppliers_archived_not_operationally_active",
            "ck_suppliers_status_valid",
            "fk_supplier_contacts_supplier_id_suppliers",
            "ck_supplier_contacts_email_or_phone_required",
        } <= constraints
        assert {
            "uq_suppliers_active_tax_identifier",
            "uq_suppliers_active_registration_number",
            "uq_supplier_contacts_active_primary_type",
        } <= indexes

        _alembic(database, "downgrade", FOUNDATION_HEAD)
        assert not asyncio.run(_supplier_tables_exist(database))

        _alembic(database, "upgrade", SUPPLIER_HEAD)
        length, _, _ = asyncio.run(_supplier_contract(database))
        assert length == "50"
    finally:
        asyncio.run(_drop_database(database))
