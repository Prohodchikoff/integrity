from dotenv import load_dotenv
from app.settings import ENVFILE_PATH
load_dotenv(ENVFILE_PATH)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.jobs.job_settings import init_job_tables
from app.core.exceptions import register_exception_handlers
from app.api.project_routes import router as project_router
from app.api.routes import router
from app.core.database import db_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_job_tables()
    yield
    await db_registry.close_all()


app = FastAPI(lifespan=lifespan)
register_exception_handlers(app)

app.include_router(router)
app.include_router(project_router)
