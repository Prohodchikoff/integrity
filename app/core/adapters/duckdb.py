import asyncio
from typing import Optional

import duckdb

from .base import BaseAdapter
from .results import RowsResult


class DuckDBAdapter(BaseAdapter):
    def __init__(self, database: str):
        super().__init__(session=None)
        self._conn = duckdb.connect(database=database)

    def _run(self, fn):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, fn)

    async def get_version(self) -> str:
        result = await self.execute("SELECT version()")
        version = result.scalar()
        if version is None:
            raise ValueError("No version returned from DuckDB")
        return str(version)

    async def execute(self, query: str, params: Optional[dict] = None) -> RowsResult:
        def _execute():
            if params:
                return self._conn.execute(query, params)
            return self._conn.execute(query)

        raw = await self._run(_execute)
        return RowsResult(raw.fetchall())

    async def create_or_replace_view(
        self, namespace: str, view_name: str, select_sql: str
    ) -> None:
        stmt = f'CREATE OR REPLACE VIEW "{namespace}"."{view_name}" AS\n{select_sql}'
        await self._run(lambda: self._conn.execute(stmt))

    async def close(self) -> None:
        await self._run(self._conn.close)