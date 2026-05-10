import re

import yaml
from pathlib import Path

from pydantic import AliasChoices, BaseModel, Field, field_validator

BUILTIN_INTEGRITY_TESTS: frozenset[str] = frozenset(
    ("not_null", "unique", "not_blank", "positive")
)

_SQL_TEST_REF_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_./-]*$")


def _validate_custom_test_ref(raw: str) -> str:
    r = raw.strip().strip("/")
    if not r or ".." in r or not _SQL_TEST_REF_PATTERN.fullmatch(r):
        raise ValueError(
            f"Invalid custom test name {raw!r}: use letters, numbers, "
            "underscores, or a nested path like 'group/my_test' (no '..')."
        )
    if r in BUILTIN_INTEGRITY_TESTS:
        raise ValueError(
            f"Custom test cannot be named {raw!r}; it is reserved for a built-in check."
        )
    return r


class ColumnTestConfig(BaseModel):
    name: str
    list_tests: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tests", "list_tests"),
    )

    model_config = {"populate_by_name": True}

    @field_validator("list_tests", mode="before")
    @classmethod
    def _coerce_legacy_sql_dict(cls, v: object) -> object:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("`tests` / `list_tests` must be a list")
        out: list[object] = []
        for item in v:
            if isinstance(item, dict) and set(item.keys()) == {"sql"}:
                out.append(item["sql"])
            elif isinstance(item, dict):
                raise ValueError(
                    f"Unknown test entry {item!r}: use a string name or legacy {{sql: path}}."
                )
            else:
                out.append(item)
        return out

    @field_validator("list_tests", mode="after")
    @classmethod
    def _normalize_test_names(cls, v: list[object]) -> list[str]:
        result: list[str] = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"Each test must be a string, got {item!r}")
            name = item.strip()
            if name in BUILTIN_INTEGRITY_TESTS:
                result.append(name)
            else:
                result.append(_validate_custom_test_ref(name))
        return result


class ModelTestConfig(BaseModel):
    model: str
    columns: list[ColumnTestConfig]


class IntegrityProjectFile(BaseModel):
    name: str
    models_dir: str = Field(
        default="models",
        description="Directory under project root with model `.sql` files.",
    )
    tests_dir: str = Field(
        default="tests",
        description="Directory under project root for custom test templates (`*.sql`).",
    )
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
