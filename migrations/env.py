from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# ✅ Import your SQLAlchemy Base and models
from src.webapp.database import Base
from src.webapp.models import *  # ensures all tables are registered

# ✅ Import database URL (sync version)
from config import SYNC_DATABASE_URL

# Alembic Config object, which provides access to .ini values
config = context.config

# ✅ Inject the database URL dynamically
config.set_main_option("sqlalchemy.url", SYNC_DATABASE_URL)

# ✅ Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Define metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode (without DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode (with real DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ✅ Decide which mode to run
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()