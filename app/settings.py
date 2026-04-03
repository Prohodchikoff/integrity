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


class MySQLConfig(BaseModel):
    type: Literal['mysql'] = 'mysql'
    host: str
    port: int = 3306
    username: str
    password: str = Field(..., repr=False)
    database: str


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
    environment: str = "dev"
    config: EnvironmentConfig

    @property
    def db_config(self):
        return self.config.db

    @property
    def dsn(self) -> str | None:
        return getattr(self.db_config, "dsn", None)


@lru_cache
def get_settings(env_name: str | None = None) -> Settings:
    current_env = env_name or os.getenv("ENVIRONMENT", "dev")

    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    env_data = data["environments"].get(current_env)

    if not env_data:
        raise ValueError(f"Environment {current_env} not found")

    return Settings.model_validate({"environment": current_env, "config": env_data})
