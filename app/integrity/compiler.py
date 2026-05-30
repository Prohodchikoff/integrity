from collections.abc import Callable

from jinja2 import StrictUndefined, Template

from app.integrity.sql_validation import validate_view_sql


def compile_sql(
    sql: str,
    ref: Callable[[str], str],
    source: Callable[[str, str], str] | None = None,
    *,
    validate: bool = True,
) -> str:
    """Render model SQL and optionally validate it for CREATE VIEW."""
    if source is None:
        def _missing_source(source_name: str, table_name: str) -> str:
            raise ValueError(
                f"source({source_name!r}, {table_name!r}) is used but no sources "
                "are configured in integrity.yml"
            )
        source = _missing_source

    rendered = Template(sql, undefined=StrictUndefined).render(
        ref=ref,
        source=source,
    ).strip()
    if validate:
        validate_view_sql(rendered)
    return rendered
