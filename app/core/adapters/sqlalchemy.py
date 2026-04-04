from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from app.settings import get_settings


def get_engine(env_name:str, async_mode: bool = False):

    setttings = get_settings(env_name).db_config

    if async_mode:
        engine = create_async_engine(
            setttings.async_url
        )
    else:
        engine = create_engine(
            setttings.url
        )

    return engine
