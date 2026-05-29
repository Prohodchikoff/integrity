from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends

from app.jobs.job_settings import JobDBSessionDep
from app.jobs.project_helpers import resolve_project_root
from app.jobs.project_jobs import (
    get_job,
    get_job_result,
    get_latest_job,
    list_jobs,
    schedule_background_job,
)
from app.jobs.project_schemas import (
    ParsedModelInfoResponse,
    ProjectJobAcceptedResponse,
    ProjectJobsListResponse,
    ProjectJobsQuery,
    ProjectJobStatusResponse,
    ProjectParseResponse,
    ProjectPathBody,
    ProjectRunBody,
    ProjectRunResponse,
    ProjectTestsResponse,
)
from app.integrity.runner import parse_project

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "/parse",
    response_model=ProjectParseResponse,
    summary="Parse project graph",
    description="Parses project models and returns execution order and model metadata.",
)
def projects_parse(body: ProjectPathBody):
    root = resolve_project_root(body.project_name)
    r = parse_project(root)
    return ProjectParseResponse(
        project_name=r.project_name,
        order=list(r.order),
        models=[ParsedModelInfoResponse.model_vaget_joblidate(m) for m in r.models],
    )


@router.post(
    "/run",
    response_model=ProjectJobAcceptedResponse,
    summary="Schedule run job",
    description="Queues an asynchronous integrity run job and returns created job id.",
)
async def projects_run_async(body: ProjectRunBody, background_tasks: BackgroundTasks):
    return schedule_background_job(background_tasks, "run", body)


@router.post(
    "/test",
    response_model=ProjectJobAcceptedResponse,
    summary="Schedule test job",
    description="Queues an asynchronous integrity test job and returns created job id.",
)
async def projects_test_async(body: ProjectRunBody, background_tasks: BackgroundTasks):
    return schedule_background_job(background_tasks, "test", body)


@router.get(
    "/jobs",
    response_model=ProjectJobsListResponse,
    summary="List jobs",
    description="Returns jobs with filters and pagination ordered from newest to oldest.",
)
async def projects_jobs_list(
    db: JobDBSessionDep,
    query: ProjectJobsQuery = Depends(),
):
    items = await list_jobs(
        project_name=query.project_name,
        kind=query.kind,
        status=query.status,
        limit=query.limit,
        offset=query.offset,
        db=db,
    )
    return ProjectJobsListResponse(
        items=items,
        limit=query.limit,
        offset=query.offset,
        returned=len(items),
    )


@router.get(
    "/jobs/latest",
    response_model=ProjectJobStatusResponse,
    summary="Get latest job",
    description="Returns the most recent job matching provided filters.",
)
async def projects_latest_job(
    db: JobDBSessionDep,
    project_name: str | None = None,
    kind: Literal["run", "test"] | None = None,
    status: Literal["queued", "running", "succeeded", "failed"] | None = None,
):
    return await get_latest_job(project_name=project_name, kind=kind, status=status, db=db)


@router.get(
    "/jobs/{job_id}",
    response_model=ProjectJobStatusResponse,
    summary="Get job status",
    description="Returns current status and progress for a single job.",
)
async def projects_job_status(job_id: str, db: JobDBSessionDep):
    return await get_job(job_id, db=db)


@router.get(
    "/jobs/{job_id}/result",
    response_model=ProjectRunResponse | ProjectTestsResponse,
    summary="Get job result",
    description="Returns final run/test result for a completed successful job.",
)
async def projects_job_result(job_id: str, db: JobDBSessionDep):
    return await get_job_result(job_id, db=db)
    