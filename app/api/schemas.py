from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.core.config import SQLDbConfig
from app.settings import Settings


class DatabaseConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password_configured: bool = False
    database: str | None = None
    schema_name: str | None = Field(default=None, serialization_alias="schema")
    sync_driver: str | None = None
    async_driver: str | None = None
    odbc_driver: str | None = None
    encrypt: str | None = None
    trust_server_certificate: str | None = None
    url_configured: bool = False
    async_url_configured: bool = False

    @classmethod
    def from_db_config(cls, db: SQLDbConfig) -> Self:
        return cls(
            type=db.type,
            host=db.host,
            port=db.port,
            username=db.username,
            password_configured=bool(db.password),
            database=db.database,
            schema_name=db.schema_name,
            sync_driver=db.sync_driver,
            async_driver=db.async_driver,
            odbc_driver=db.odbc_driver,
            encrypt=db.encrypt,
            trust_server_certificate=db.trust_server_certificate,
            url_configured=bool(db.sync_dsn),
            async_url_configured=bool(db.async_dsn),
        )


class EnvironmentConfigPublic(BaseModel):
    type: str
    connection: DatabaseConfig


class SettingsPublicResponse(BaseModel):
    project_name: str
    project_root: Path
    environment: str
    config: EnvironmentConfigPublic

    @classmethod
    def from_settings(cls, settings: Settings) -> Self:
        db = settings.db_config
        return cls(
            project_name=settings.project_name,
            project_root=settings.project_root,
            environment=settings.environment,
            config=EnvironmentConfigPublic(
                type=settings.config.type,
                connection=DatabaseConfig.from_db_config(db),
            ),
        )


class ProjectsListResponse(BaseModel):
    projects: list[str]


class ConnectionTestResponse(BaseModel):
    database_type: str
    version: str | None = None
