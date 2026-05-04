from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession


class BaseAdapter(ABC):
    def __init__(self, session: AsyncSession):
        self.session = session

    @abstractmethod
    async def execute(self, query: str, params: Optional[dict] = None):
        pass
