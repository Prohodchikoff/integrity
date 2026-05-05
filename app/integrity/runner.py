import time
from dataclasses import dataclass
from pathlib import Path

from app.core.adapters.base import BaseAdapter
from app.integrity.compiler import compile_sql
from app.integrity.dag import topological_order
from app.integrity.project import discover_model_paths, load_project_file
from app.integrity.refs import extract_ref_names, validate_refs
from app.integrity.relation import quoted_relation
from app.settings import Settings, get_settings


@dataclass
class LoadedProject:
    project_name: str
    paths: dict[str, Path]
    graph: dict[str, set[str]]
    raw_sql: dict[str, str]


@dataclass
class ParsedModelInfo:
    name: str
    path: str
    refs: tuple[str, ...]


@dataclass
class ParseResult:
    project_name: str
    models: tuple[ParsedModelInfo, ...]
    order: tuple[str, ...]


@dataclass
class RunModelResult:
    name: str
    ok: bool
    error: str | None = None
    elapsed_ms: float | None = None


@dataclass
class RunResult:
    project_name: str
    order: tuple[str, ...]
    models: tuple[RunModelResult, ...]


def execution_namespace(settings: Settings) -> str:
    db = settings.db_config
    if db.type == "postgresql":
        return db.schema_name
    if db.type == "mysql":
        return db.database
    raise ValueError(f"Unsupported database type: {db.type!r}")


def load_project_graph(project_root: Path) -> LoadedProject:
    root = project_root.resolve()
    meta = load_project_file(root)
    paths = discover_model_paths(root, meta.models_dir)
    known = set(paths)

    raw_sql: dict[str, str] = {}
    graph: dict[str, set[str]] = {}

    for name, path in paths.items():
        raw = path.read_text(encoding="utf-8")
        raw_sql[name] = raw
        refs = extract_ref_names(raw)
        errs = validate_refs(name, refs, known)
        if errs:
            raise ValueError("; ".join(errs))
        graph[name] = set(refs)

    return LoadedProject(
        project_name=meta.name,
        paths=paths,
        graph=graph,
        raw_sql=raw_sql,
    )


def parse_project(project_root: Path) -> ParseResult:
    loaded = load_project_graph(project_root)
    order = topological_order(loaded.graph)
    model_infos = [
        ParsedModelInfo(
            name=name,
            path=str(loaded.paths[name]),
            refs=tuple(sorted(loaded.graph[name])),
        )
        for name in sorted(loaded.paths)
    ]
    return ParseResult(
        project_name=loaded.project_name,
        models=tuple(model_infos),
        order=order,
    )


async def run_project(
    project_root: Path,
    adapter: BaseAdapter,
    env_name: str | None = None,
    *,
    _loaded: LoadedProject | None = None,
) -> RunResult:
    settings = get_settings(env_name)
    db_type = settings.db_config.type
    namespace = execution_namespace(settings)

    loaded = _loaded or load_project_graph(project_root)
    order = topological_order(loaded.graph)
    known = set(loaded.paths)

    results: list[RunModelResult] = []

    def ref_cb(model_name: str) -> str:
        if model_name not in known:
            raise ValueError(f"ref({model_name!r}) is not a known model")
        return quoted_relation(db_type, namespace, model_name)

    for name in order:
        t0 = time.perf_counter()
        try:
            compiled = compile_sql(loaded.raw_sql[name], ref_cb)
            await adapter.create_or_replace_view(namespace, name, compiled)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            results.append(
                RunModelResult(
                    name=name,
                    ok=False,
                    error=str(e),
                    elapsed_ms=round(elapsed_ms, 2),
                )
            )
            break

        elapsed_ms = (time.perf_counter() - t0) * 1000
        results.append(
            RunModelResult(
                name=name,
                ok=True,
                error=None,
                elapsed_ms=round(elapsed_ms, 2),
            )
        )

    return RunResult(
        project_name=loaded.project_name, order=order, models=tuple(results)
    )
