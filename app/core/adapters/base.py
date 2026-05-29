from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession


class BaseAdapter(ABC):
    def __init__(self, session: AsyncSession | None = None):
        self.session = session

    @abstractmethod
    async def execute(self, query: str, params: Optional[dict] = None):
        pass

    @abstractmethod
    async def create_or_replace_view(
        self, namespace: str, view_name: str, select_sql: str
    ) -> None:
        pass

    @abstractmethod
    async def get_version(self) -> str:
        pass

    async def close(self) -> None:
        return None
