from fastapi import APIRouter
from app.settings import get_settings, list_projects, reload_settings_cache
from app.api.dependencies import DBAdapterDep
from app.core.database import db_registry
from app.api.schemas import (
    ConfigReloadResponse,
    ConnectionTestResponse,
    ProjectsListResponse,
    SettingsPublicResponse,
)

router = APIRouter()


@router.get(
    "/config",
    response_model=SettingsPublicResponse,
    summary="Get resolved config",
    description="Returns the resolved project configuration for the selected project/environment.",
)
def config(project_name: str, env_name: str | None = None) -> SettingsPublicResponse:
    settings = get_settings(env_name=env_name, project_name=project_name)
    return SettingsPublicResponse.from_settings(settings)


@router.get(
    "/projects",
    response_model=ProjectsListResponse,
    summary="List configured projects",
    description="Returns all project names available in the environments configuration.",
)
def projects() -> ProjectsListResponse:
    return ProjectsListResponse(projects=list_projects())


@router.get(
    "/test_connection",
    response_model=ConnectionTestResponse,
    summary="Check database connection",
    description="Tests the active adapter connection and returns database type and version.",
)
async def test_connection(adapter: DBAdapterDep) -> ConnectionTestResponse:
    version = await adapter.get_version()
    return ConnectionTestResponse(
        database_type=adapter.__class__.__name__,
        version=version,
    )


@router.post(
    "/config/reload",
    response_model=ConfigReloadResponse,
    summary="Reload environments config",
    description=(
        "Clears cached environments.yaml settings and closes open DB managers "
        "so the next request picks up file changes without restarting the app."
    ),
)
async def reload_config() -> ConfigReloadResponse:
    reload_settings_cache()
    await db_registry.close_all()
    return ConfigReloadResponse(status="reloaded", projects=list_projects())
