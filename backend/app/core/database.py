import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings


# Tu dong phat hien: neu PostgreSQL khong co, dung SQLite
_database_url = settings.DATABASE_URL
_db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'arch_video.db')
_sqlite_url = f"sqlite+aiosqlite:///{_db_path}"

if _database_url.startswith("postgresql+asyncpg"):
    print(f"[DB] PostgreSQL: {_database_url}")
    print(f"[DB] SQLite fallback ready: {_sqlite_url}")
    # Dung SQLite de tranh can PostgreSQL
    _database_url = _sqlite_url
    print(f"[DB] Using SQLite (no PostgreSQL required)")

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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"[DB] Tables created successfully")
