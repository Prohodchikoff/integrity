from jinja2 import StrictUndefined, Template


def render_user_test(
    template: str,
    *,
    relation: str,
    column: str,
    column_name: str,
    db_type: str,
) -> str:
    """Render custom test SQL; placeholders: relation, column (quoted id), column_name, db_type."""
    return Template(template, undefined=StrictUndefined).render(
        relation=relation,
        column=column,
        column_name=column_name,
        db_type=db_type,
    ).strip()


def build_not_null_sql(relation: str, column: str) -> str:
    stmt = f"""
    SELECT * FROM {relation} WHERE {column} IS NULL
    """.strip()

    return stmt


def build_unique_sql(relation: str, column: str, db_type: str) -> str:
    if db_type == "postgresql":
        cond = f"t2.{column} IS NOT DISTINCT FROM t.{column}"
    elif db_type == "mysql":
        cond = f"t2.{column} <=> t.{column}"
    else:
        raise ValueError(f"Unsupported db_type for unique test: {db_type!r}")
    stmt = f"""
    SELECT * FROM {relation} t
    WHERE (
        SELECT COUNT(*) FROM {relation} t2
        WHERE {cond}
    ) > 1
    """.strip()
    return stmt


def build_not_blank_sql(relation: str, column: str) -> str:
    stmt = f"""
    SELECT * FROM {relation}
    WHERE {column} IS NULL OR TRIM({column}) = ''
    """.strip()
    return stmt


def build_positive_sql(relation: str, column: str) -> str:
    stmt = f"""
    SELECT * FROM {relation}
    WHERE {column} IS NOT NULL AND {column} <= 0
    """.strip()
    return stmt
