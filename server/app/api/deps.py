"""Reusable FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import async_session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async session, commit on success, rollback on exception."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SessionDep = Depends(get_db_session)
