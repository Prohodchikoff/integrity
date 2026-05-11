def quoted_relation(db_type: str, namespace: str, model_name: str) -> str:
    kind = db_type.strip().lower()
    if kind in {
        "postgresql",
        "clickhouse",
        "duckdb",
        "trino",
        "redshift",
        "snowflake",
        "oracle",
    }:
        return f'"{namespace}"."{model_name}"'
    if kind in {"mysql", "mariadb", "bigquery"}:
        if kind == "bigquery":
            return f"`{namespace}.{model_name}`"
        return f"`{namespace}`.`{model_name}`"
    if kind == "mssql":
        return f"[{namespace}].[{model_name}]"
    raise ValueError(f"Unsupported db_type for relation quoting: {db_type!r}")
