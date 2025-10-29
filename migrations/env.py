# migrations/env.py
from __future__ import annotations
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ---- import your app bits ----
from config import ASYNC_DATABASE_URL           # your DSN
from src.webapp.database import Base            # your Declarative Base
# Ensure models are imported so tables register on Base.metadata:
from src.webapp import models  # noqa: F401  (keep this import!)

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# >>> THIS is what autogenerate uses
target_metadata = Base.metadata

# Put the URL into Alembic config (used for offline & engine_from_config)
config.set_main_option("sqlalchemy.url", ASYNC_DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode'."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,          # detect type changes too
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,          # detect type changes too
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()