from pathlib import Path
from typing import Literal, Any, Annotated, Union
from functools import lru_cache
import os
import yaml
from pydantic import BaseModel, Field, computed_field, model_validator


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "environments.yaml"


class PostgresConfig(BaseModel):
    type: Literal['postgresql'] = 'postgresql'
    host: str
    port: int = 5432
    username: str
    password: str = Field(..., repr=False)
    database: str
    schema_name: str = Field("public", alias="schema")

    @computed_field
    @property
    def async_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @computed_field
    @property
    def url(self) -> str:
        return self.async_url.replace("postgresql+asyncpg", "postgresql+psycopg")


class MySQLConfig(BaseModel):
    type: Literal['mysql'] = 'mysql'
    host: str
    port: int = 3306
    username: str
    password: str = Field(..., repr=False)
    database: str

    @computed_field
    @property
    def async_url(self) -> str:
        return f"mysql+aiomysql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"

    @computed_field
    @property
    def url(self) -> str:
        return self.async_url.replace("mysql+aiomysql", "mysql")


DbConfig = Annotated[Union[PostgresConfig, MySQLConfig], Field(discriminator="type")]


class EnvironmentConfig(BaseModel):
    type: Literal["postgresql", "mysql"]
    connection: dict[str, Any]

    db: DbConfig = Field(..., alias="connection")

    @model_validator(mode="before")
    @classmethod
    def inject_type(cls, data: Any):
        if isinstance(data, dict):
            conn = data.get("connection") or data.get("db")
            if isinstance(conn, dict) and "type" not in conn:
                conn = dict(conn)
                conn["type"] = data.get("type")
                data = dict(data)
                data["connection"] = conn
        return data


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
