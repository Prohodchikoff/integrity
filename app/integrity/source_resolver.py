from collections.abc import Callable

from app.integrity.relation import quoted_relation
from app.integrity.sources import SourceConfig


def make_source_resolver(
    db_type: str,
    default_namespace: str,
    sources: dict[str, SourceConfig],
) -> Callable[[str, str], str]:
    def source_cb(source_name: str, table_name: str) -> str:
        src = sources.get(source_name)
        if src is None:
            known = ", ".join(sorted(sources)) or "(none configured)"
            raise ValueError(
                f"Unknown source {source_name!r}. Declared sources: {known}"
            )
        physical_table = src.resolve_table(table_name)
        namespace = src.schema or default_namespace
        return quoted_relation(db_type, namespace, physical_table)

    return source_cb
