import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncGenerator, AsyncIterator

from fastapi import Depends
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base


DATABASE_URL = os.getenv("JOB_DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "JOB_DATABASE_URL is required (e.g. mysql+aiomysql://user:pass@host:3306/jobs)"
    )

Base = declarative_base()


class DatabaseSessionManager:
    def __init__(self, host: str, engine_kwargs: dict[str, Any] | None = None):
        kwargs = engine_kwargs or {}
        self._engine = create_async_engine(host, **kwargs)
        self._sessionmaker = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self._engine,
        )

    async def close(self) -> None:
        if self._engine is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")
        await self._engine.dispose()
        self._engine = None
        self._sessionmaker = None

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[AsyncConnection]:
        if self._engine is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")
        async with self._engine.begin() as connection:
            try:
                yield connection
            except Exception:
                await connection.rollback()
                raise

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        if self._sessionmaker is None:
            raise RuntimeError("DatabaseSessionManager is not initialized")
        session = self._sessionmaker()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


sessionmanager = DatabaseSessionManager(
    DATABASE_URL,
    {"pool_pre_ping": True},
)


class JobStatusRow(Base):
    __tablename__ = "integrity_job_statuses"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), unique=True, index=True, nullable=False)
    kind = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, index=True)
    project_name = Column(String(128), nullable=False, index=True)
    env_name = Column(String(128), nullable=True, index=True)
    created_at = Column(String(64), nullable=False)
    started_at = Column(String(64), nullable=True)
    finished_at = Column(String(64), nullable=True)
    progress_done = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=True)
    error_text = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)


class JobEventRow(Base):
    __tablename__ = "integrity_job_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(64), index=True, nullable=False)
    event_kind = Column(String(32), nullable=False)
    item_name = Column(String(255), nullable=True)
    status = Column(String(16), nullable=False)
    error_text = Column(Text, nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(String(64), nullable=False)


async def init_job_tables() -> None:
    async with sessionmanager.connect() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_job_db() -> AsyncGenerator[AsyncSession, None]:
    async with sessionmanager.session() as session:
        yield session


async def close_job_db() -> None:
    await sessionmanager.close()


JobDBSessionDep = Annotated[AsyncSession, Depends(get_job_db)]
