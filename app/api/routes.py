from fastapi import APIRouter
from app.settings import get_settings, list_projects
from app.api.dependecies import DBAdapterDep

router = APIRouter()


@router.get('/config')
def config(project_name: str, env_name: str | None = None):
    settings = get_settings(env_name=env_name, project_name=project_name)

    return settings


@router.get("/projects")
def projects():
    return {"projects": list_projects()}


@router.get('/test_connection')
async def test_connection(adapter: DBAdapterDep):
    result = await adapter.execute("SELECT version()")
    return result.scalar()


@router.get("/test_connection_factory")
async def test_connection_factory(adapter: DBAdapterDep):

    version = await adapter.execute("SELECT version()")

    return {
        "database_type": adapter.__class__.__name__,
        "version": version.scalar(),
    }
