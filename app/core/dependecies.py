from typing import Annotated, AsyncGenerator
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import DatabaseManager, db_registry
from app.core.adapters.base import BaseAdapter


def get_db_manager(
    project_name: str = Query(..., alias="project"),
    env_name: str | None = Query(None, alias="env"),
) -> DatabaseManager:
    return db_registry.get_manager(project_name=project_name, env_name=env_name)


async def get_db(
    db_manager: "DatabaseManagerDep",
) -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.get_session() as session:
        yield session


async def get_db_adapter(
    db: "DBSessionDep",
    db_manager: "DatabaseManagerDep",
) -> BaseAdapter:
    return db_manager.create_adapter(db)


DatabaseManagerDep = Annotated[DatabaseManager, Depends(get_db_manager)]
DBSessionDep = Annotated[AsyncSession, Depends(get_db)]
DBAdapterDep = Annotated[BaseAdapter, Depends(get_db_adapter)]
