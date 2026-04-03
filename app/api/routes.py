from fastapi import APIRouter
from app.settings import get_settings


router = APIRouter()


@router.get('/config')
def config(env_name: str | None = None):
    settings = get_settings(env_name)

    return settings
