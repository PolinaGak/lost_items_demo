from typing import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import config


class Base(DeclarativeBase):
    __abstract__ = True


async_engine = create_async_engine(
    config.DATABASE_URL_ASYNC,
    echo=config.DEBUG,
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine = create_engine(
    config.DATABASE_URL,
    echo=config.DEBUG,
    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(sync_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    from app.core.synthetic_data import generate_synthetic_data

    async with async_engine.begin() as conn:
        if config.DEBUG:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        print("Database tables created")

    await generate_synthetic_data()
    print("Synthetic data loaded")



async def close_db() -> None:
    await async_engine.dispose()
    sync_engine.dispose()
    print("✅ Database connections closed")