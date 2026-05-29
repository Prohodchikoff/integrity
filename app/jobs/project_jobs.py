from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.project_helpers import resolve_project_root
from app.jobs.job_settings import JobEventRow, JobStatusRow, sessionmanager
from app.jobs.project_schemas import (
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

logger = logging.getLogger(__name__)


def _merge_job_error(job: ProjectJobStatusResponse, message: str) -> str:
    if job.error:
        return f"{job.error}; {message}"
    return message


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


async def _try_mark_job_failed(job: ProjectJobStatusResponse, error: str) -> bool:
    message = error[:4000]
    finished_at = utc_now()
    try:
        async with sessionmanager.session() as db:
            try:
                row = await db.scalar(select(JobStatusRow).where(JobStatusRow.job_id == job.job_id))
                if row is None:
                    row = JobStatusRow(
                        job_id=job.job_id,
                        kind=job.kind,
                        status="failed",
                        project_name=job.project_name,
                        env_name=job.env,
                        created_at=job.created_at,
                        started_at=job.started_at,
                        finished_at=finished_at,
                        progress_done=job.progress_done,
                        progress_total=job.progress_total,
                        error_text=message,
                    )
                    db.add(row)
                else:
                    row.status = "failed"
                    row.error_text = message
                    row.finished_at = finished_at
                await db.commit()
                return True
            except SQLAlchemyError:
                await db.rollback()
                raise
    except SQLAlchemyError as exc:
        logger.warning(
            "Could not persist failed job status job_id=%s (jobs DB unavailable): %s",
            job.job_id,
            exc,
        )
        return False


async def _persist_job_snapshot(job: ProjectJobStatusResponse, *, background: bool = False) -> None:
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
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception(
                "Failed to persist job snapshot job_id=%s status=%s",
                job.job_id,
                job.status,
            )
            if background:
                message = f"Failed to persist job status: {exc}"
                job.status = "failed"
                job.error = _merge_job_error(job, message)
                job.finished_at = utc_now()
                persisted = await _try_mark_job_failed(job, job.error)
                if not persisted:
                    logger.warning(
                        "Job %s marked failed in memory only; jobs DB was unavailable",
                        job.job_id,
                    )
            raise


async def _record_job_progress(
    job_id: str,
    *,
    event_kind: str,
    item_name: str | None,
    event_status: str,
    payload: dict[str, Any] | None = None,
    error: str | None = None,
    background: bool = False,
    job_ctx: ProjectJobStatusResponse | None = None,
) -> None:
    async with sessionmanager.session() as db:
        try:
            updated = await db.execute(
                update(JobStatusRow)
                .where(JobStatusRow.job_id == job_id)
                .values(progress_done=JobStatusRow.progress_done + 1)
            )
            if updated.rowcount == 0:
                raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

            db.add(
                JobEventRow(
                    job_id=job_id,
                    event_kind=event_kind,
                    item_name=item_name,
                    status=event_status,
                    error_text=error,
                    payload_json=None if payload is None else json.dumps(payload),
                    created_at=utc_now(),
                )
            )
            await db.commit()
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception(
                "Failed to record job progress job_id=%s event_kind=%s item_name=%s",
                job_id,
                event_kind,
                item_name,
            )
            if background and job_ctx is not None:
                message = f"Failed to record job progress: {exc}"
                job_ctx.status = "failed"
                job_ctx.error = _merge_job_error(job_ctx, message)
                job_ctx.finished_at = utc_now()
                if not await _try_mark_job_failed(job_ctx, job_ctx.error):
                    logger.warning(
                        "Job %s marked failed in memory only; jobs DB was unavailable",
                        job_id,
                    )
            raise


async def execute_run(
    body: ProjectRunBody,
    job_id: str | None = None,
    job_ctx: ProjectJobStatusResponse | None = None,
) -> ProjectRunResponse:
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
            await _record_job_progress(
                job_id,
                event_kind="model",
                item_name=item.name,
                event_status="succeeded" if item.ok else "failed",
                payload={"elapsed_ms": item.elapsed_ms},
                error=item.error,
                background=True,
                job_ctx=job_ctx,
            )

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


async def execute_test(
    body: ProjectRunBody,
    job_id: str | None = None,
    job_ctx: ProjectJobStatusResponse | None = None,
) -> ProjectTestsResponse:
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
            await _record_job_progress(
                job_id,
                event_kind="test",
                item_name=item.test_id,
                event_status="succeeded" if item.ok else "failed",
                payload={"fail_count": item.fail_count},
                error=item.error,
                background=True,
                job_ctx=job_ctx,
            )

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
    background_tasks.add_task(_persist_job_snapshot, job, background=True)

    async def _job_runner() -> None:
        job.status = "running"
        job.started_at = utc_now()
        try:
            await _persist_job_snapshot(job, background=True)
            if kind == "run":
                root = resolve_project_root(body.project_name)
                loaded = load_project_graph(root)
                job.progress_total = len(loaded.graph)
                await _persist_job_snapshot(job, background=True)
                response = await execute_run(body, job_id=job_id, job_ctx=job)
            else:
                root = resolve_project_root(body.project_name)
                job.progress_total = planned_test_count(root)
                await _persist_job_snapshot(job, background=True)
                response = await execute_test(body, job_id=job_id, job_ctx=job)
            job.status = "succeeded"
            job.result = response.model_dump()
        except Exception as exc:
            job.status = "failed"
            job.error = str(exc)
        finally:
            job.finished_at = utc_now()
            try:
                snapshot = await _get_job_with_new_session(job_id)
                snapshot.status = job.status
                snapshot.result = job.result
                snapshot.error = job.error
                snapshot.finished_at = job.finished_at
                snapshot.progress_total = job.progress_total
                await _persist_job_snapshot(snapshot, background=True)
            except SQLAlchemyError:
                pass

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
