from pathlib import Path
from functools import lru_cache
import os
import yaml
from pydantic import BaseModel, Field

from app.core.config import EnvironmentConfig


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "environments.yaml"
ENVFILE_PATH = BASE_DIR.parent / '.env'


class Settings(BaseModel):
    project_name: str
    project_root: Path
    environment: str = "dev"
    config: EnvironmentConfig

    @property
    def db_config(self):
        return self.config.db

    @property
    def dsn(self) -> str | None:
        return getattr(self.db_config, "dsn", None)


class ProjectSettings(BaseModel):
    project_root: str | None = Field(
        default=None,
        description="Path to project root with integrity.yml. Relative paths are resolved from app/.",
    )
    default_environment: str | None = None
    environments: dict[str, EnvironmentConfig] = Field(
        ...,
        validation_alias="environment",
    )

    def resolve_project_root(self, project_name: str) -> Path:
        if self.project_root:
            root = Path(self.project_root)
            if not root.is_absolute():
                root = (BASE_DIR / root).resolve()
            return root
        return (BASE_DIR / "config" / project_name).resolve()

    def resolve_environment(self, env_name: str | None) -> str:
        if env_name:
            return env_name
        if self.default_environment:
            return self.default_environment
        if self.environments:
            return next(iter(self.environments))
        raise ValueError("Project has no configured environments")


class ConfigFile(BaseModel):
    projects: dict[str, ProjectSettings]


@lru_cache(maxsize=1)
def get_config() -> ConfigFile:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return ConfigFile.model_validate(data)


def list_projects() -> list[str]:
    return sorted(get_config().projects.keys())


@lru_cache
def get_settings(
    project_name: str,
    env_name: str | None = None,
) -> Settings:
    config = get_config()
    project = config.projects.get(project_name)
    if not project:
        raise ValueError(f"Project {project_name!r} not found")

    current_env = project.resolve_environment(env_name or os.getenv("ENVIRONMENT"))
    env_data = project.environments.get(current_env)
    if not env_data:
        raise ValueError(
            f"Environment {current_env!r} not found for project {project_name!r}"
        )

    return Settings.model_validate(
        {
            "project_name": project_name,
            "project_root": project.resolve_project_root(project_name),
            "environment": current_env,
            "config": env_data,
        }
    )
