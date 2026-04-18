from typing import Annotated
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import db_manager


async def get_db(
    env_name: str = Query("dev", alias="env"),
):

    await db_manager.init(env_name=env_name)

    async with db_manager.get_session() as session:
        yield session


DBSessionDep = Annotated[AsyncSession, Depends(get_db)]
