import re
from collections.abc import Iterable

REF_PATTERN = re.compile(
    r"""\{\{\s*ref\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*\)\s*\}\}""",
    re.IGNORECASE | re.DOTALL,
)

SOURCE_PATTERN = re.compile(
    r"""\{\{\s*source\s*\(\s*['\"](?P<source>[^'\"]+)['\"]\s*,\s*['\"](?P<table>[^'\"]+)['\"]\s*\)\s*\}\}""",
    re.IGNORECASE | re.DOTALL,
)


def extract_ref_names(sql: str) -> set[str]:
    return {m.group("name") for m in REF_PATTERN.finditer(sql)}


def extract_source_refs(sql: str) -> set[tuple[str, str]]:
    return {
        (m.group("source"), m.group("table"))
        for m in SOURCE_PATTERN.finditer(sql)
    }


def validate_refs(model_name: str, refs: Iterable[str], known_models: set[str]) -> list[str]:
    errors: list[str] = []
    for r in refs:
        if r not in known_models:
            errors.append(
                f"Model {model_name!r} references unknown model {r!r} (ref must name another .sql model)."
            )
    return errors


def validate_sources(
    model_name: str,
    source_refs: Iterable[tuple[str, str]],
    sources: dict[str, set[str]],
) -> list[str]:
    errors: list[str] = []
    for source_name, table_name in source_refs:
        tables = sources.get(source_name)
        if tables is None:
            errors.append(
                f"Model {model_name!r} references unknown source {source_name!r}."
            )
            continue
        if table_name not in tables:
            errors.append(
                f"Model {model_name!r} references unknown table {table_name!r} "
                f"on source {source_name!r}."
            )
    return errors
