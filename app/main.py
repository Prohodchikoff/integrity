from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.jobs.job_settings import init_job_tables
from app.api.project_routes import router as project_router
from app.api.routes import router
from app.core.database import db_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_job_tables()
    yield
    await db_registry.close_all()


app = FastAPI(lifespan=lifespan)

app.include_router(router)
app.include_router(project_router)
