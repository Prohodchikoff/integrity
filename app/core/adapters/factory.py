from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseAdapter
from .sqlalchemy_base import SqlalchemyAdapter
from .clickhouse import ClickHouseAdapter


_SQLALCHEMY_ADAPTERS = {
    "postgresql", "mysql", "mariadb", "mssql",
    "duckdb", "bigquery", "oracle", "trino",
    "redshift", "snowflake",
}

def get_adapter(
    db_type: str,
    session: Optional[AsyncSession] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> BaseAdapter:
    db_kind = db_type.strip().lower()

    if db_kind in _SQLALCHEMY_ADAPTERS:
        if session is None:
            raise ValueError(f"session is required for db_type={db_type!r}")
        return SqlalchemyAdapter(session=session)

    if db_kind == "clickhouse":
        return ClickHouseAdapter(
            host=host or "localhost",
            port=port or 8123,
            username=username or "default",
            password=password or "",
            database=database or "default",
        )

    raise ValueError(f"Unsupported database type: {db_type!r}")