from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from app.settings import get_settings


class DatabaseManager:
    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None
        self._current_env: Optional[str] = None
        self._initialized = False

    async def init(self, env_name: Optional[str] = None) -> None:

        if self._initialized and self._current_env == env_name:
            return

        if self._initialized:
            await self.close()

        settings = get_settings(env_name=env_name)

        pool_kwargs = {
            "pool_size": 15,
            "max_overflow": 25,
            "pool_pre_ping": False,
            "pool_recycle": 3600,
            "pool_timeout": 30,
        }

        self._engine = create_async_engine(settings.db_config.async_url, **pool_kwargs)

        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        self._current_env = settings.environment
        self._initialized = True

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            self._initialized = False

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self._sessionmaker:
            raise RuntimeError(
                "DatabaseManager not initialized. Call await db_manager.init() first."
            )

        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception as e:
                print(e)
                await session.rollback()
                raise
            finally:
                await session.close()


db_manager = DatabaseManager()
