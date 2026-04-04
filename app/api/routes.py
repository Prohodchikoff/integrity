from fastapi import APIRouter
from sqlalchemy import text
from app.settings import get_settings
from app.core.adapters.sqlalchemy import get_engine

router = APIRouter()


@router.get('/config')
def config(env_name: str | None = None):
    settings = get_settings(env_name)

    return settings

@router.get('/test_connection')
def test_connection(env_name: str | None = None):
    engine = get_engine(env_name)

    with engine.connect() as conn:
        result = conn.execute(text('SELECT version();')).scalar()

    return result

@router.get('/test_connection_async')
async def test_connection_async(env_name: str | None = None):
    engine = get_engine(env_name, True)

    async with engine.connect() as conn:
        result = await conn.execute(text('SELECT version();'))

    return result.scalar()
