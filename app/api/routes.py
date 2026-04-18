from fastapi import APIRouter, status
from fastapi.exceptions import HTTPException
from sqlalchemy import text
from app.settings import get_settings
from app.core.dependecies import DBSessionDep

router = APIRouter()


@router.get('/config')
def config(env_name: str | None = None):
    settings = get_settings(env_name)

    return settings


@router.get('/test_connection')
async def test_connection(db: DBSessionDep):
    try:
        result = await db.execute(text('SELECT version();'))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
    return result.scalar()
