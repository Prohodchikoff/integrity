from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.project_helpers import resolve_project_root
from app.jobs.job_settings import JobEventRow, JobStatusRow, sessionmanager
from app.jobs.project_sсhemas import (
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
from app.integrity.test_runner import planned_test_count, run_project_tests


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump_result(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value)


def _json_load_result(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _row_to_job(row: JobStatusRow) -> ProjectJobStatusResponse:
    payload: dict[str, Any] = {
        "job_id": row.job_id,
        "kind": row.kind,
        "status": row.status,
        "project_name": row.project_name,
        "env": row.env_name,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "progress_done": row.progress_done or 0,
        "progress_total": row.progress_total,
        "error": row.error_text,
    }
    result = _json_load_result(row.result_json)
    if result is not None:
        payload["result"] = result
    return ProjectJobStatusResponse.model_validate(payload)


async def _persist_job_snapshot(job: ProjectJobStatusResponse) -> None:
    async with sessionmanager.session() as db:
        try:
            row = await db.scalar(select(JobStatusRow).where(JobStatusRow.job_id == job.job_id))
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
            row.result_json = None if job.result is None else _json_dump_result(job.result)
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise


async def _append_event(
    job: ProjectJobStatusResponse,
    event_kind: str,
    item_name: str | None,
    status: str,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    async with sessionmanager.session() as db:
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
            await db.commit()
        except SQLAlchemyError:
            await db.rollback()
            raise


async def execute_run(body: ProjectRunBody, job_id: str | None = None) -> ProjectRunResponse:
    root = resolve_project_root(body.project_name)
    loaded = load_project_graph(root)

    manager = db_registry.get_manager(
        env_name=body.env,
        project_name=body.project_name,
    )
    async with manager.get_session() as session:
        adapter = manager.create_adapter(session)

        async def _on_model_result(item):
            if not job_id:
                return
            job = await _get_job_with_new_session(job_id)
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
        finally:
            await adapter.close()

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
            job = await _get_job_with_new_session(job_id)
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
        finally:
            await adapter.close()

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
    background_tasks.add_task(_persist_job_snapshot, job)

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
                job.progress_total = planned_test_count(root)
                await _persist_job_snapshot(job)
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


async def get_job(job_id: str, db: AsyncSession | None = None) -> ProjectJobStatusResponse:
    if db is not None:
        return await _get_job(job_id=job_id, db=db)
    async with sessionmanager.session() as db:
        return await _get_job(job_id=job_id, db=db)


async def _get_job_with_new_session(job_id: str) -> ProjectJobStatusResponse:
    async with sessionmanager.session() as db:
        return await _get_job(job_id=job_id, db=db)


async def _get_job(job_id: str, db: AsyncSession) -> ProjectJobStatusResponse:
    row = await db.scalar(select(JobStatusRow).where(JobStatusRow.job_id == job_id))
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return _row_to_job(row)


async def list_jobs(
    project_name: str | None = None,
    kind: Literal["run", "test"] | None = None,
    status: Literal["queued", "running", "succeeded", "failed"] | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession | None = None,
) -> list[ProjectJobStatusResponse]:
    if db is not None:
        return await _list_jobs(
            db=db,
            project_name=project_name,
            kind=kind,
            status=status,
            limit=limit,
            offset=offset,
        )
    async with sessionmanager.session() as db:
        return await _list_jobs(
            db=db,
            project_name=project_name,
            kind=kind,
            status=status,
            limit=limit,
            offset=offset,
        )


async def _list_jobs(
    db: AsyncSession,
    project_name: str | None = None,
    kind: Literal["run", "test"] | None = None,
    status: Literal["queued", "running", "succeeded", "failed"] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[ProjectJobStatusResponse]:
    query = select(JobStatusRow)
    if project_name:
        query = query.where(JobStatusRow.project_name == project_name)
    if kind:
        query = query.where(JobStatusRow.kind == kind)
    if status:
        query = query.where(JobStatusRow.status == status)

    query = query.order_by(desc(JobStatusRow.created_at)).offset(max(offset, 0)).limit(max(limit, 0))
    rows = (await db.scalars(query)).all()
    return [_row_to_job(row) for row in rows]


async def get_latest_job(
    project_name: str | None = None,
    kind: Literal["run", "test"] | None = None,
    status: Literal["queued", "running", "succeeded", "failed"] | None = None,
    db: AsyncSession | None = None,
) -> ProjectJobStatusResponse:
    jobs = await list_jobs(project_name=project_name, kind=kind, status=status, limit=1, offset=0, db=db)
    if not jobs:
        raise HTTPException(status_code=404, detail="No jobs found for provided filters")
    return jobs[0]


async def get_job_result(job_id: str, db: AsyncSession | None = None) -> ProjectRunResponse | ProjectTestsResponse:
    if db is not None:
        job = await _get_job(job_id=job_id, db=db)
    else:
        job = await get_job(job_id)
    if job.status in {"queued", "running"}:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not finished yet: {job_id}",
        )
    if job.status == "failed":
        raise HTTPException(
            status_code=409,
            detail=job.error or f"Job failed: {job_id}",
        )
    if job.result is None:
        raise HTTPException(
            status_code=500,
            detail=f"Job finished without result: {job_id}",
        )
    return job.result
