"""
Database session management.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ── Async Engine (FastAPI) ────────────────────────────────────
async_engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Sync Engine (Alembic only - lazy init) ───────────────────
# Created lazily to avoid localhost connection errors at import time
_sync_engine = None
_SyncSessionLocal = None


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        from sqlalchemy import create_engine
        _sync_engine = create_engine(
            settings.sync_database_url,
            echo=False,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_sync_session():
    global _SyncSessionLocal
    if _SyncSessionLocal is None:
        from sqlalchemy.orm import sessionmaker
        _SyncSessionLocal = sessionmaker(bind=get_sync_engine(), autoflush=False, autocommit=False)
    return _SyncSessionLocal


# Backward compat aliases
@property
def sync_engine():
    return get_sync_engine()


@property  
def SyncSessionLocal():
    return get_sync_session()
