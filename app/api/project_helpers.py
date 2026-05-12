from pathlib import Path

from fastapi import HTTPException

from app.settings import get_settings


def resolve_project_root(project_name: str) -> Path:
    root = get_settings(project_name=project_name).project_root
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Project directory not found: {root}")
    return root
