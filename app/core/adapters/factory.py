from .base import BaseAdapter
from .postgresql import PostgresqlAdapter
from .mysql import MysqlAdapter
from sqlalchemy.ext.asyncio import AsyncSession


def get_adapter(session: AsyncSession, db_type: str) -> BaseAdapter:

    adapters = {
        "postgresql": PostgresqlAdapter,
        "mysql": MysqlAdapter,
    }

    if db_type not in adapters:
        raise ValueError(f"Unsupported database type: {db_type}")

    adapter_class = adapters[db_type]

    return adapter_class(session=session)
