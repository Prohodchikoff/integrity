import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from app.settings import get_settings


logger = logging.getLogger("uvicorn.error")


class DatabaseManager:
    def __init__(self, env_name: Optional[str] = None):
        settings = get_settings(env_name=env_name)
        self._environment: str = settings.environment
        self._db_type: str = settings.db_config.type

        pool_kwargs = {
            "pool_size": 15,
            "max_overflow": 25,
            "pool_pre_ping": False,
            "pool_recycle": 3600,
            "pool_timeout": 30,
        }

        self._engine = create_async_engine(settings.db_config.async_url, **pool_kwargs)
        self._register_engine_events(
            environment=self._environment,
            db_type=self._db_type,
        )

        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info("Database engine initialized environment=%s, db_type=%s", self._environment, self._db_type)

    async def close(self) -> None:
        if self._engine:
            logger.info("Disposing database engine environment=%s, db_type=%s", self._environment, self._db_type)

            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None

    @property
    def environment(self) -> str:
        return self._environment

    @property
    def db_type(self) -> str:
        return self._db_type

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        if not self._sessionmaker:
            raise RuntimeError("DatabaseManager is closed.")

        async with self._sessionmaker() as session:
            try:
                yield session
            except Exception:
                logger.exception("Database session error environment=%s, db_type=%s", self._environment, self._db_type)

                await session.rollback()
                raise
            finally:
                await session.close()

    def _register_engine_events(self, environment: str, db_type: str) -> None:
        if not self._engine:
            return

        sync_engine = self._engine.sync_engine

        @event.listens_for(sync_engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            logger.info("Database physical connection opened environment=%s, db_type=%s, connection_record_id=%s", self._environment, self._db_type, connection_record)


        @event.listens_for(sync_engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("Database connection checked out from pool environment=%s, db_type=%s, connection_record_id=%s", self._environment, self._db_type, connection_record)

        @event.listens_for(sync_engine, "checkin")
        def on_checkin(dbapi_connection, connection_record):
            logger.debug("Database connection returned to pool environment=%s, db_type=%s, connection_record_id=%s", self._environment, self._db_type, connection_record)


        @event.listens_for(sync_engine, "close")
        def on_close(dbapi_connection, connection_record):
            logger.info("Database physical connection closed environment=%s, db_type=%s, connection_record_id=%s", self._environment, self._db_type, connection_record)

        @event.listens_for(sync_engine, "handle_error")
        def on_handle_error(exception_context):
            logger.exception("Database connection/pool error nvironment=%s, db_type=%s, is_disconnect=%s, is_pre_ping=%s", self._environment, self._db_type, exception_context.is_disconnect, exception_context.is_pre_ping)


class DatabaseRegistry:
    def __init__(self):
        self._managers: dict[str, DatabaseManager] = {}

    def get_manager(self, env_name: Optional[str] = None) -> DatabaseManager:
        settings = get_settings(env_name=env_name)
        environment = settings.environment

        if environment not in self._managers:
            self._managers[environment] = DatabaseManager(env_name=environment)

        return self._managers[environment]

    async def close_all(self) -> None:
        for manager in self._managers.values():
            await manager.close()
        self._managers.clear()


db_registry = DatabaseRegistry()
