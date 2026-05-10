from dataclasses import dataclass
from pathlib import Path

from app.core.adapters.base import BaseAdapter
from app.integrity.project import (
    BUILTIN_INTEGRITY_TESTS,
    discover_model_paths,
    load_project_file,
)
from app.integrity.relation import quoted_relation
from app.integrity.runner import execution_namespace
from app.integrity.test_compiler import (
    build_not_blank_sql,
    build_not_null_sql,
    build_positive_sql,
    build_unique_sql,
    render_user_test,
)
from app.settings import get_settings


@dataclass
class TestResult:
    test_id: str
    model: str
    column: str
    type: str
    ok: bool
    fail_count: int
    error: str | None = None


@dataclass
class TestRunResult:
    project_name: str
    tests: tuple[TestResult, ...]


def _quote_column(db_type: str, column: str) -> str:
    if db_type == "postgresql":
        return f'"{column}"'
    if db_type == "mysql":
        return f"`{column}`"
    raise ValueError(f"Unsupported db_type for column quoting: {db_type!r}")


def _resolve_test_file(root: Path, tests_dir: str, ref: str) -> Path:
    base = (root / tests_dir).resolve()
    candidate = (base / ref).with_suffix(".sql").resolve()
    try:
        candidate.relative_to(base)
    except ValueError as e:
        raise ValueError(
            f"SQL test path {ref!r} resolves outside {tests_dir!r}"
        ) from e
    if not candidate.is_file():
        raise FileNotFoundError(
            f"SQL test file not found: {candidate} "
            f"(expected under {base})"
        )
    return candidate


def _build_builtin_sql(test_type: str, relation: str, column: str, db_type: str) -> str:
    quoted_column = _quote_column(db_type, column)
    if test_type == "not_null":
        return build_not_null_sql(relation, quoted_column)
    if test_type == "unique":
        return build_unique_sql(relation, quoted_column, db_type)
    if test_type == "not_blank":
        return build_not_blank_sql(relation, quoted_column)
    if test_type == "positive":
        return build_positive_sql(relation, quoted_column)
    raise ValueError(f"Unsupported test type: {test_type}")


async def run_project_tests(
    project_root: Path,
    adapter: BaseAdapter,
    env_name: str | None = None,
) -> TestRunResult:
    root = project_root.resolve()
    settings = get_settings(env_name)
    db_type = settings.db_config.type
    namespace = execution_namespace(settings)

    project = load_project_file(root)
    known_models = set(discover_model_paths(root, project.models_dir).keys())
    results: list[TestResult] = []

    for model_cfg in project.tests:
        model_name = model_cfg.model
        if model_name not in known_models:
            raise ValueError(
                f"Test config references unknown model {model_name!r}. "
                "Define model SQL file first."
            )
        relation = quoted_relation(db_type, namespace, model_name)

        for column_cfg in model_cfg.columns:
            column_name = column_cfg.name
            for test_name in column_cfg.list_tests:
                type_label = test_name
                test_id = f"{model_name}.{column_name}.{test_name}"
                try:
                    if test_name in BUILTIN_INTEGRITY_TESTS:
                        sql = _build_builtin_sql(
                            test_name, relation, column_name, db_type
                        )
                    else:
                        path = _resolve_test_file(
                            root, project.tests_dir, test_name
                        )
                        raw_tpl = path.read_text(encoding="utf-8")
                        quoted = _quote_column(db_type, column_name)
                        sql = render_user_test(
                            raw_tpl,
                            relation=relation,
                            column=quoted,
                            column_name=column_name,
                            db_type=db_type,
                        )
                except Exception as exc:
                    results.append(
                        TestResult(
                            test_id=test_id,
                            model=model_name,
                            column=column_name,
                            type=type_label,
                            ok=False,
                            fail_count=0,
                            error=str(exc),
                        )
                    )
                    continue

                try:
                    count_stmt = (
                        f"SELECT COUNT(*) FROM ({sql}) AS integrity_test_failures"
                    )
                    count_result = await adapter.execute(count_stmt)
                    fail_count = int(count_result.scalar_one())
                    results.append(
                        TestResult(
                            test_id=test_id,
                            model=model_name,
                            column=column_name,
                            type=type_label,
                            ok=fail_count == 0,
                            fail_count=fail_count,
                            error=None,
                        )
                    )
                except Exception as exc:
                    results.append(
                        TestResult(
                            test_id=test_id,
                            model=model_name,
                            column=column_name,
                            type=type_label,
                            ok=False,
                            fail_count=0,
                            error=str(exc),
                        )
                    )

    return TestRunResult(project_name=project.name, tests=tuple(results))
