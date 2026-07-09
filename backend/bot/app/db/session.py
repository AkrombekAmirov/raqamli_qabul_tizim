"""Async DB engine va session factory. Ulanish retry bilan.

Jadvallar Alembic migratsiyalari orqali yaratiladi (entrypoint.sh).
Bu modul faqat engine, session va DB tayyorligini kutish (wait_for_db)
bilan shug'ullanadi.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings

log = structlog.get_logger()
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=False,
    # 10k+ foydalanuvchi uchun kattaroq pool. DB max_connections=500
    # bo'lgani uchun bu qiymatlar xavfsiz.
    pool_size=20,
    max_overflow=40,
    pool_timeout=30,
    pool_pre_ping=True,   # uzilgan ulanishlarni avtomatik tekshiradi
    pool_recycle=1800,
)

SessionFactory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def wait_for_db() -> None:
    """DB ulanishi tayyor bo'lguncha kutadi (oddiy SELECT 1)."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info("database_connection_ready")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = SessionFactory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
