from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import router
from app.core.database import db_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await db_registry.close_all()


app = FastAPI(lifespan=lifespan)

app.include_router(router)
