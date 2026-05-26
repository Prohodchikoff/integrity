from fastapi import APIRouter
from app.settings import get_settings, list_projects
from app.api.dependencies import DBAdapterDep
from app.api.schemas import SettingsPublicResponse

router = APIRouter()


@router.get("/config", response_model=SettingsPublicResponse)
def config(project_name: str, env_name: str | None = None) -> SettingsPublicResponse:
    settings = get_settings(env_name=env_name, project_name=project_name)
    return SettingsPublicResponse.from_settings(settings)


@router.get("/projects")
def projects():
    return {"projects": list_projects()}


@router.get("/test_connection")
async def test_connection(adapter: DBAdapterDep):
    version = await adapter.execute("SELECT version()")
    return {
        "database_type": adapter.__class__.__name__,
        "version": version.scalar(),
    }
