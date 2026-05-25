from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.api.project_helpers import resolve_project_root
from app.api.job_settings import JobEventRow, JobStatusRow, SessionLocal
from app.api.project_models import (
    ProjectJobAcceptedResponse,
    ProjectJobStatusResponse,
    ProjectRunBody,
    ProjectRunResponse,
    ProjectTestsResponse,
    RunModelResultResponse,
    TestResultItemResponse,
    TestSummaryResponse,
)
from app.core.database import db_registry
from app.integrity.runner import load_project_graph, run_project
from app.integrity.test_runner import run_project_tests

_project_jobs: dict[str, ProjectJobStatusResponse] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _persist_job_snapshot(job: ProjectJobStatusResponse) -> None:
    db = SessionLocal()
    try:
        row = db.query(JobStatusRow).filter(JobStatusRow.job_id == job.job_id).first()
        if row is None:
            row = JobStatusRow(job_id=job.job_id)
            db.add(row)
        row.kind = job.kind
        row.status = job.status
        row.project_name = job.project_name
        row.env_name = job.env
        row.created_at = job.created_at
        row.started_at = job.started_at
        row.finished_at = job.finished_at
        row.progress_done = job.progress_done
        row.progress_total = job.progress_total
        row.error_text = job.error
        row.result_json = None if job.result is None else json.dumps(job.result)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()


async def _append_event(
    job: ProjectJobStatusResponse,
    event_kind: str,
    item_name: str | None,
    status: str,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        row = JobEventRow(
            job_id=job.job_id,
            event_kind=event_kind,
            item_name=item_name,
            status=status,
            error_text=error,
            payload_json=None if payload is None else json.dumps(payload),
            created_at=utc_now(),
        )
        db.add(row)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
    finally:
        db.close()


async def execute_run(body: ProjectRunBody, job_id: str | None = None) -> ProjectRunResponse:
    root = resolve_project_root(body.project_name)
    try:
        loaded = load_project_graph(root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    manager = db_registry.get_manager(
        env_name=body.env,
        project_name=body.project_name,
    )
    async with manager.get_session() as session:
        adapter = manager.create_adapter(session)

        async def _on_model_result(item):
            if not job_id:
                return
            job = _project_jobs[job_id]
            job.progress_done += 1
            await _append_event(
                job,
                event_kind="model",
                item_name=item.name,
                status="succeeded" if item.ok else "failed",
                payload={"elapsed_ms": item.elapsed_ms},
                error=item.error,
            )
            await _persist_job_snapshot(job)

        try:
            result = await run_project(
                root,
                adapter,
                env_name=body.env,
                project_name=body.project_name,
                on_model_result=_on_model_result if job_id else None,
                _loaded=loaded,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    return ProjectRunResponse(
        project_name=result.project_name,
        order=list(result.order),
        models=[RunModelResultResponse.model_validate(m) for m in result.models],
    )


async def execute_test(body: ProjectRunBody, job_id: str | None = None) -> ProjectTestsResponse:
    root = resolve_project_root(body.project_name)
    manager = db_registry.get_manager(
        env_name=body.env,
        project_name=body.project_name,
    )
    async with manager.get_session() as session:
        adapter = manager.create_adapter(session)

        async def _on_test_result(item):
            if not job_id:
                return
            job = _project_jobs[job_id]
            job.progress_done += 1
            await _append_event(
                job,
                event_kind="test",
                item_name=item.test_id,
                status="succeeded" if item.ok else "failed",
                payload={"fail_count": item.fail_count},
                error=item.error,
            )
            await _persist_job_snapshot(job)

        try:
            result = await run_project_tests(
                root,
                adapter,
                env_name=body.env,
                project_name=body.project_name,
                on_test_result=_on_test_result if job_id else None,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    total = len(result.tests)
    failed = sum(1 for t in result.tests if not t.ok)
    passed = total - failed
    return ProjectTestsResponse(
        project_name=result.project_name,
        summary=TestSummaryResponse(total=total, passed=passed, failed=failed),
        tests=[TestResultItemResponse.model_validate(t) for t in result.tests],
    )


def schedule_background_job(
    background_tasks: BackgroundTasks,
    kind: Literal["run", "test"],
    body: ProjectRunBody,
) -> ProjectJobAcceptedResponse:
    job_id = str(uuid4())
    job = ProjectJobStatusResponse(
        job_id=job_id,
        kind=kind,
        status="queued",
        project_name=body.project_name,
        env=body.env,
        created_at=utc_now(),
    )
    _project_jobs[job_id] = job

    async def _job_runner() -> None:
        job.status = "running"
        job.started_at = utc_now()
        await _persist_job_snapshot(job)
        try:
            if kind == "run":
                root = resolve_project_root(body.project_name)
                loaded = load_project_graph(root)
                job.progress_total = len(loaded.graph)
                await _persist_job_snapshot(job)
                response = await execute_run(body, job_id=job_id)
            else:
                root = resolve_project_root(body.project_name)
                response = await execute_test(body, job_id=job_id)
            job.status = "succeeded"
            job.result = response.model_dump()
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = utc_now()
            await _persist_job_snapshot(job)

    background_tasks.add_task(_job_runner)
    return ProjectJobAcceptedResponse(job_id=job_id, status="queued")


def get_job(job_id: str) -> ProjectJobStatusResponse:
    job = _project_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job
