from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.adapters.factory import get_adapter
from app.core.database import db_registry
from app.integrity.runner import load_project_graph, parse_project, run_project
from app.integrity.test_runner import run_project_tests

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectPathBody(BaseModel):
    project_root: str = Field(
        ...,
        description="Absolute path to a directory containing integrity.yml",
    )


class ProjectRunBody(ProjectPathBody):
    env: str = Field(
        "dev",
        description="Environment profile from app/config/environments.yaml (database connection).",
    )


def _resolve_project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise HTTPException(
            status_code=400, detail=f"project_root is not a directory: {root}"
        )
    return root


@router.post("/parse")
def projects_parse(body: ProjectPathBody):
    root = _resolve_project_root(body.project_root)
    try:
        r = parse_project(root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {
        "project_name": r.project_name,
        "order": list(r.order),
        "models": [
            {"name": m.name, "path": m.path, "refs": list(m.refs)} for m in r.models
        ],
    }


@router.post("/run")
async def projects_run(body: ProjectRunBody):
    root = _resolve_project_root(body.project_root)
    try:
        loaded = load_project_graph(root)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    manager = db_registry.get_manager(env_name=body.env)
    async with manager.get_session() as session:
        adapter = get_adapter(session=session, db_type=manager.db_type)
        try:
            result = await run_project(
                root, adapter, env_name=body.env, _loaded=loaded
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "project_name": result.project_name,
        "order": list(result.order),
        "models": [
            {
                "name": m.name,
                "ok": m.ok,
                "error": m.error,
                "elapsed_ms": m.elapsed_ms,
            }
            for m in result.models
        ],
    }

@router.post(
    "/test",
    summary="Run integrity tests",
)
async def projects_test(body: ProjectRunBody):
    root = _resolve_project_root(body.project_root)

    manager = db_registry.get_manager(env_name=body.env)
    async with manager.get_session() as session:
        adapter = get_adapter(session=session, db_type=manager.db_type)
        try:
            result = await run_project_tests(
                root, adapter, env_name=body.env,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    total = len(result.tests)
    failed = sum(1 for t in result.tests if not t.ok)
    passed = total - failed
    return {
        "project_name": result.project_name,
        "summary": {"total": total, "passed": passed, "failed": failed},
        "tests": [
            {
                "test_id": t.test_id,
                "model": t.model,
                "column": t.column,
                "type": t.type,
                "ok": t.ok,
                "fail_count": t.fail_count,
                "error": t.error,
            }
            for t in result.tests
        ],
    }
