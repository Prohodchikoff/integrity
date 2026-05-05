from collections.abc import Callable

from jinja2 import StrictUndefined, Template


def _source_not_implemented(*_a, **_kw) -> str:
    raise NotImplementedError(
        "source() is not implemented in phase 1; use ref() to reference models."
    )


def compile_sql(
    sql: str,
    ref: Callable[[str], str],
) -> str:
    return Template(sql, undefined=StrictUndefined).render(
        ref=ref,
        source=_source_not_implemented,
    )
