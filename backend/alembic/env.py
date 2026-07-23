from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# --------------------------------------------------------------------
# Add backend directory to Python path before importing project modules
# --------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db import Base
from app.modules.execution import models as execution_models  # noqa: F401
from app.modules.catalog import models as catalog_models  # noqa: F401
from app.modules.inventory import models as inventory_models  # noqa: F401

# --------------------------------------------------------------------
# Alembic configuration
# --------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# --------------------------------------------------------------------
# Offline migrations
# --------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# --------------------------------------------------------------------
# Online migrations
# --------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    """Configure Alembic and run migrations."""

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using SQLAlchemy AsyncEngine."""

    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    asyncio.run(run_async_migrations())


# --------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
