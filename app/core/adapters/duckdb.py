import asyncio
from typing import Optional

import duckdb

from .base import BaseAdapter


class DuckDBResult:
    def __init__(self, relation):
        self._rows = relation.fetchall()

    def scalar_one(self):
        if not self._rows:
            raise ValueError("No rows returned")
        if len(self._rows) > 1:
            raise ValueError(f"Expected one row, got {len(self._rows)}")
        return self._rows[0][0]

    def scalar(self):
        if not self._rows:
            return None
        return self._rows[0][0]


class DuckDBAdapter(BaseAdapter):
    def __init__(self, database: str):
        super().__init__(session=None)
        self._conn = duckdb.connect(database=database)

    def _run(self, fn):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, fn)

    async def execute(self, query: str, params: Optional[dict] = None) -> DuckDBResult:
        def _execute():
            if params:
                return self._conn.execute(query, params)
            return self._conn.execute(query)

        raw = await self._run(_execute)
        return DuckDBResult(raw)

    async def create_or_replace_view(
        self, namespace: str, view_name: str, select_sql: str
    ) -> None:
        stmt = f'CREATE OR REPLACE VIEW "{namespace}"."{view_name}" AS\n{select_sql}'
        await self._run(lambda: self._conn.execute(stmt))