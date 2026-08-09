"""Baza ulanishi va sessiya."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

def make_engine(url: str) -> AsyncEngine:
    """Baza uchun engine. asyncpg'ga ulanish vaqti cheklanadi."""
    connect_args: dict = {}
    if "asyncpg" in url:
        # Baza javob bermasa cheksiz kutib qolmaslik uchun
        connect_args = {"timeout": 10, "command_timeout": 60}
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        connect_args=connect_args,
        echo=False,
    )


engine = make_engine(settings.database_url)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def rebind(url: str) -> None:
    """Boshqa baza manziliga o'tish (ichki xost topilmaganda zaxiraga)."""
    global engine
    previous = engine
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
    settings.database_url = url
    await previous.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency — har so'rov uchun bitta sessiya."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Bot va scheduler ichida qo'lda ishlatish uchun."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
