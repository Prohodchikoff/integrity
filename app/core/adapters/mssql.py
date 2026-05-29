import asyncio
from typing import Optional

import aioodbc

from .base import BaseAdapter
from .results import RowsResult

DEFAULT_ODBC_DRIVER = "ODBC Driver 18 for SQL Server"
DEFAULT_PORT = 1433


class MssqlAdapter(BaseAdapter):
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        database: str,
        odbc_driver: str = DEFAULT_ODBC_DRIVER,
        encrypt: str = "yes",
        trust_server_certificate: str = "yes",
    ):
        super().__init__(session=None)
        self._dsn = (
            f"DRIVER={{{odbc_driver}}};"
            f"SERVER={host},{port};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            f"Encrypt={encrypt};"
            f"TrustServerCertificate={trust_server_certificate};"
        )
        self._conn: aioodbc.Connection | None = None
        self._lock = asyncio.Lock()

    async def _connection(self) -> aioodbc.Connection:
        if self._conn is None:
            self._conn = await aioodbc.connect(dsn=self._dsn, autocommit=False)
        return self._conn

    async def get_version(self) -> str:
        result = await self.execute("SELECT @@VERSION AS version")
        version = result.scalar()
        if version is None:
            raise ValueError("No version returned from MSSQL")
        return str(version)

    async def execute(self, query: str, params: Optional[dict] = None) -> RowsResult:
        if params:
            raise NotImplementedError("MSSQL adapter does not support named params")
        async with self._lock:
            conn = await self._connection()
            async with conn.cursor() as cur:
                await cur.execute(query)
                rows = await cur.fetchall() if cur.description else []
                if not query.strip().upper().startswith("SELECT"):
                    await conn.commit()
                return RowsResult(rows)

    async def create_or_replace_view(
        self, namespace: str, view_name: str, select_sql: str
    ) -> None:
        stmt = (
            f"CREATE OR ALTER VIEW [{namespace}].[{view_name}] AS\n{select_sql}"
        )
        await self.execute(stmt)

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
