import asyncio
from typing import Optional

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from .base import BaseAdapter
from sqlalchemy.ext.asyncio import AsyncSession


class ClickHouseResult:
    """Wrapper щоб імітувати SQLAlchemy Result interface."""

    def __init__(self, query_result):
        self._result = query_result

    def scalar_one(self):
        rows = self._result.result_rows
        if not rows:
            raise ValueError("No rows returned")
        if len(rows) > 1:
            raise ValueError(f"Expected one row, got {len(rows)}")
        return rows[0][0]

    def scalar(self):
        rows = self._result.result_rows
        if not rows:
            return None
        return rows[0][0]


class ClickHouseAdapter(BaseAdapter):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
    ):
        super().__init__(session=None)  # type: ignore[arg-type]
        self._client: Client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
        )

    def _run(self, fn):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, fn)

    async def execute(self, query: str, params: Optional[dict] = None) -> ClickHouseResult:
        raw = await self._run(lambda: self._client.query(query))
        return ClickHouseResult(raw)

    async def create_or_replace_view(
        self, namespace: str, view_name: str, select_sql: str
    ) -> None:
        stmt = (
            f"CREATE OR REPLACE VIEW `{namespace}`.`{view_name}` AS\n{select_sql}"
        )
        await self._run(lambda: self._client.command(stmt))