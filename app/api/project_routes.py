from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api.project_helpers import resolve_project_root
from app.api.project_jobs import execute_run, execute_test, get_job, schedule_background_job
from app.api.project_models import (
    ParsedModelInfoResponse,
    ProjectJobAcceptedResponse,
    ProjectJobStatusResponse,
    ProjectParseResponse,
    ProjectPathBody,
    ProjectRunBody,
    ProjectRunResponse,
    ProjectTestsResponse,
)
from app.integrity.runner import parse_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/parse", response_model=ProjectParseResponse)
def projects_parse(body: ProjectPathBody):
    root = resolve_project_root(body.project_name)
    try:
        r = parse_project(root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ProjectParseResponse(
        project_name=r.project_name,
        order=list(r.order),
        models=[ParsedModelInfoResponse.model_validate(m) for m in r.models],
    )


@router.post("/run", response_model=ProjectRunResponse)
async def projects_run(body: ProjectRunBody):
    return await execute_run(body)


@router.post("/run_async", response_model=ProjectJobAcceptedResponse)
async def projects_run_async(body: ProjectRunBody, background_tasks: BackgroundTasks):
    return schedule_background_job(background_tasks, "run", body)

@router.post(
    "/test",
    summary="Run integrity tests",
    response_model=ProjectTestsResponse,
)
async def projects_test(body: ProjectRunBody):
    return await execute_test(body)


@router.post("/test_async", response_model=ProjectJobAcceptedResponse)
async def projects_test_async(body: ProjectRunBody, background_tasks: BackgroundTasks):
    return schedule_background_job(background_tasks, "test", body)


@router.get("/jobs/{job_id}", response_model=ProjectJobStatusResponse)
async def projects_job_status(job_id: str):
    return get_job(job_id)
