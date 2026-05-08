import yaml
from pathlib import Path
from pydantic import BaseModel, Field


class ColumnTestConfig(BaseModel):
    name: str
    list_tests: list[str] = Field(default_factory=list, alias="tests")

    model_config = {"populate_by_name": True}

class ModelTestConfig(BaseModel):
    model: str
    columns: list[ColumnTestConfig]

class IntegrityProjectFile(BaseModel):
    name: str
    models_dir: str = "models"
    tests: list[ModelTestConfig] = Field(default_factory=list)

def load_project_file(project_root: Path) -> IntegrityProjectFile:
    root = project_root.resolve()
    cfg = root / "integrity.yml"
    if not cfg.is_file():
        raise FileNotFoundError(f"Missing integrity.yml under {root}")
    data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    return IntegrityProjectFile.model_validate(data)


def discover_model_paths(project_root: Path, models_dir: str) -> dict[str, Path]:
    root = project_root.resolve()
    base = root / models_dir
    if not base.is_dir():
        raise FileNotFoundError(f"Models directory not found: {base}")

    models: dict[str, Path] = {}
    for path in sorted(base.rglob("*.sql")):
        rel = path.relative_to(base)
        name = "_".join(rel.with_suffix("").parts)
        if name in models:
            raise ValueError(
                f"Duplicate model name {name!r}: {models[name]} and {path}"
            )
        models[name] = path
    return models
