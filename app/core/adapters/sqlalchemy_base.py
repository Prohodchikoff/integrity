from typing import Optional
from sqlalchemy import text
from .base import BaseAdapter


class SqlalchemyAdapter(BaseAdapter):
    async def execute(self, query: str, params: Optional[dict] = None):
        result = await self.session.execute(text(query), params or {})

        if not query.strip().upper().startswith(("SELECT", "SHOW", "DESCRIBE")):
            await self.session.commit()
        return result
