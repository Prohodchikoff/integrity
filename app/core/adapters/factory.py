from .base import BaseAdapter
from .sqlalchemy_base import SqlalchemyAdapter
from sqlalchemy.ext.asyncio import AsyncSession


def get_adapter(session: AsyncSession, db_type: str) -> BaseAdapter:

    db_kind = db_type.strip().lower()
    adapters = {
        "postgresql": SqlalchemyAdapter,
        "mysql": SqlalchemyAdapter,
        "mariadb": SqlalchemyAdapter,
        "mssql": SqlalchemyAdapter,
        "clickhouse": SqlalchemyAdapter,
        "duckdb": SqlalchemyAdapter,
        "bigquery": SqlalchemyAdapter,
        "oracle": SqlalchemyAdapter,
        "trino": SqlalchemyAdapter,
        "redshift": SqlalchemyAdapter,
        "snowflake": SqlalchemyAdapter,
    }

    if db_kind not in adapters:
        raise ValueError(f"Unsupported database type: {db_type}")

    adapter_class = adapters[db_kind]

    return adapter_class(session=session)
