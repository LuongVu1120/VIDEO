from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .config import settings
from .database import get_db
from ..models.user import User

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_EMAIL = "admin@archgen.ai"
DEFAULT_USER_NAME = "Admin"


async def get_or_create_default_user(db: AsyncSession) -> User:
    """Get or create the single default user for this single-user app."""
    result = await db.execute(select(User).where(User.id == DEFAULT_USER_ID))
    user = result.scalar_one_or_none()
    if user:
        return user

    user = User(
        id=DEFAULT_USER_ID,
        email=DEFAULT_USER_EMAIL,
        hashed_password="",
        full_name=DEFAULT_USER_NAME,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(
    db: AsyncSession = Depends(get_db),
) -> User:
    """Always returns the single default user — no login required."""
    return await get_or_create_default_user(db)
