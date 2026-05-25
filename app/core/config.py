from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator


DEFAULT_SYNC_DRIVERS: dict[str, str] = {
    "postgresql": "psycopg",
    "mysql": "pymysql",
    "mariadb": "pymysql",
    "mssql": "pyodbc",
    "clickhouse": "connect",
    "duckdb": "duckdb_engine",
    "oracle": "oracledb",
    "bigquery": "pybigquery",
    "trino": "trino",
    "redshift": "psycopg2",
    "snowflake": "snowflake",
}

DEFAULT_ASYNC_DRIVERS: dict[str, str] = {
    "postgresql": "asyncpg",
    "mysql": "aiomysql",
    "mssql": "aioodbc",
    # "clickhouse": "asynch",
}


class SQLDbConfig(BaseModel):
    type: str
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = Field(default=None, repr=False)
    database: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")

    sync_dsn: str | None = Field(default=None, alias="url")
    async_dsn: str | None = Field(default=None, alias="async_url")
    sync_driver: str | None = None
    async_driver: str | None = None

    @model_validator(mode="after")
    def validate_db_type_and_minimum_connection(self) -> "SQLDbConfig":
        db_type = self.type.strip().lower()

        self.type = db_type
        if self.sync_dsn or self.async_dsn:
            return self

        if not self.host and self.type not in {"duckdb", "bigquery"}:
            raise ValueError(
                "Provide `url`/`async_url` or host-based fields for SQL connection"
            )
        if self.type == "duckdb" and not self.database:
            raise ValueError("database path is required for DuckDB")
        return self

    @computed_field
    @property
    def async_url(self) -> str:
        if self.async_dsn:
            return self.async_dsn
        if self.sync_dsn and "+async" in self.sync_dsn:
            return self.sync_dsn

        driver = self.async_driver or DEFAULT_ASYNC_DRIVERS.get(self.type)
        if driver:
            return self._build_url(driver)

        if self.sync_dsn:
            return self.sync_dsn
        return self._build_url(self.sync_driver or DEFAULT_SYNC_DRIVERS.get(self.type))

    @computed_field
    @property
    def url(self) -> str:
        if self.sync_dsn:
            return self.sync_dsn
        return self._build_url(self.sync_driver or DEFAULT_SYNC_DRIVERS.get(self.type))

    def _build_url(self, driver: str | None) -> str:
        scheme = self.type if not driver else f"{self.type}+{driver}"
        credentials = ""
        if self.username:
            credentials = self.username
            if self.password:
                credentials = f"{credentials}:{self.password}"
            credentials = f"{credentials}@"

        host = self.host or ""
        port = f":{self.port}" if self.port else ""
        database = f"/{self.database}" if self.database else ""
        return f"{scheme}://{credentials}{host}{port}{database}"


class EnvironmentConfig(BaseModel):
    type: str
    connection: dict[str, Any]

    db: SQLDbConfig = Field(..., alias="connection")

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
