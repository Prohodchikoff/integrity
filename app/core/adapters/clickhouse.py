import asyncio
from typing import Optional

import clickhouse_connect
from clickhouse_connect.driver.client import Client

from .base import BaseAdapter
from .results import RowsResult


class ClickHouseAdapter(BaseAdapter):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
    ):
        super().__init__(session=None)
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

    async def get_version(self) -> str:
        result = await self.execute("SELECT version()")
        version = result.scalar()
        if version is None:
            raise ValueError("No version returned from ClickHouse")
        return str(version)

    async def execute(self, query: str, params: Optional[dict] = None) -> RowsResult:
        raw = await self._run(lambda: self._client.query(query))
        return RowsResult(raw.result_rows)

    async def create_or_replace_view(
        self, namespace: str, view_name: str, select_sql: str
    ) -> None:
        stmt = (
            f"CREATE OR REPLACE VIEW `{namespace}`.`{view_name}` AS\n{select_sql}"
        )
        await self._run(lambda: self._client.command(stmt))

    async def close(self) -> None:
        await self._run(self._client.close)