import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings


# Database URL selection
# Production: always use PostgreSQL (set FORCE_POSTGRES=true in .env)
# Development: auto-fallback to SQLite if PostgreSQL is unavailable
_database_url = settings.DATABASE_URL
_db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'arch_video.db')
_sqlite_url = f"sqlite+aiosqlite:///{_db_path}"

if settings.FORCE_POSTGRES:
    if not _database_url.startswith("postgresql"):
        raise RuntimeError(
            "FORCE_POSTGRES=true but DATABASE_URL is not PostgreSQL. "
            "Set a valid PostgreSQL DATABASE_URL or disable FORCE_POSTGRES."
        )
    print(f"[DB] PostgreSQL (forced): {_database_url}")
elif _database_url.startswith("postgresql+asyncpg"):
    _database_url = _sqlite_url
    print(f"[DB] PostgreSQL configured but dev mode — using SQLite: {_sqlite_url}")
    print(f"[DB] Set FORCE_POSTGRES=true in production to require PostgreSQL")
else:
    print(f"[DB] Using: {_database_url}")

engine = create_async_engine(_database_url, echo=settings.DEBUG)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all database tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"[DB] Tables created successfully")
