"""SQLAlchemy 2.x async base + engine + session factory.

Import all model modules from app/db/models/__init__.py so they register
on Base.metadata before alembic autogenerate runs.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.settings import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_settings = get_settings()

engine: AsyncEngine = create_async_engine(
    str(_settings.database.url),
    echo=_settings.database.echo,
    pool_size=_settings.database.pool_size,
    max_overflow=_settings.database.max_overflow,
    pool_timeout=_settings.database.pool_timeout_seconds,
    pool_recycle=_settings.database.pool_recycle_seconds,
    pool_pre_ping=True,
)

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def dispose_engine() -> None:
    """Call from lifespan shutdown."""
    await engine.dispose()
