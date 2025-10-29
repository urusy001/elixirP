import json
from logging import getLogger, Logger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, inspect
from config import ASYNC_DATABASE_URL
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_size=10,          # realistic default for async apps
    max_overflow=20,       # allow up to 30 concurrent (10 + 20 overflow)
    pool_timeout=60,       # seconds to wait before raising TimeoutError
    pool_recycle=1800,     # recycle every 30 mins to avoid stale sockets
    pool_pre_ping=True,    # ensures dropped connections are refreshed
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

class BaseModelMixin:
    """Adds universal to_dict() and to_json() methods to SQLAlchemy models."""

    def to_dict(self) -> dict:
        """Convert the SQLAlchemy object to a clean dictionary."""
        return {
            c.key: getattr(self, c.key)
            for c in inspect(self).mapper.column_attrs
        }

    def to_json(self) -> str:
        """Convert the SQLAlchemy object to a JSON string."""
        return json.dumps(self.to_dict(), default=str)

Base = declarative_base(cls=BaseModelMixin)

async def init_db(recreate: bool):
    logger = getLogger(__name__)
    async with engine.begin() as conn:
        if recreate:
            logger.warning("Recreating entire database schema...")
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            logger.info("All tables dropped and recreated successfully.")
        else:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("All tables checked/created successfully.")

    logger.info("DB initialization complete.")

# ---------------- GET ASYNC SESSION ----------------
async def get_db() -> AsyncSession:
    """Provide a single async session per request, with rollback on exception."""
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ---------------- CLEAR TABLES ----------------
async def clear_tables(logger: Logger) -> None:
    """Truncate all data tables (except alembic_version) safely using autocommit."""
    try:
        # Create a connection in AUTOCOMMIT mode
        async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
            # Fetch all public tables
            result = await conn.execute(text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename != 'alembic_version';
            """))
            tables = [row[0] for row in result]

            if not tables:
                logger.warning("No tables found to clear")
                return

            table_list = ", ".join(f'"{t}"' for t in tables)
            logger.info(f"Clearing tables: {table_list}")

            # TRUNCATE with RESTART IDENTITY CASCADE
            await conn.execute(
                text(f"TRUNCATE {table_list} RESTART IDENTITY CASCADE;")
            )
            logger.info("Tables cleared successfully")

    except Exception as e:
        logger.error(f"Failed to clear tables: {e}")
        raise

async def get_db_items(logger: Logger) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """))
        tables = [row[0] for row in result.fetchall()]

        if not tables:
            logger.warning("No tables found in database")
            return

        for table in tables:
            logger.info(f"📋 Table: {table}")
            try:
                res = await conn.execute(text(f'SELECT * FROM "{table}";'))
                rows = res.fetchall()  # ✅ await needed
                if not rows:
                    logger.info("  (empty)")
                    continue
                colnames = res.keys()
                logger.info("  Columns: " + ", ".join(colnames))
                for row in rows:
                    logger.info("  " + str(dict(zip(colnames, row))))
            except Exception as e:
                logger.error(f"  Failed to fetch {table}: {e}")
