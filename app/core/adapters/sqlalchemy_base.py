from typing import Optional
from sqlalchemy import text
from .base import BaseAdapter


class SqlalchemyAdapter(BaseAdapter):
    async def execute(self, query: str, params: Optional[dict] = None):
        result = await self.session.execute(text(query), params or {})

        if not query.strip().upper().startswith(("SELECT", "SHOW", "DESCRIBE")):
            await self.session.commit()
        return result

    async def create_or_replace_view(
        self, namespace: str, view_name: str, select_sql: str
    ) -> None:
        bind = self.session.sync_session.get_bind()
        dialect = bind.dialect.name
        if dialect == "postgresql":
            stmt = f'CREATE OR REPLACE VIEW "{namespace}"."{view_name}" AS\n{select_sql}'
        elif dialect in ("mysql", "mariadb"):
            stmt = f"CREATE OR REPLACE VIEW `{namespace}`.`{view_name}` AS\n{select_sql}"
        else:
            raise NotImplementedError(f"Unsupported dialect for views: {dialect}")
        await self.execute(stmt)
