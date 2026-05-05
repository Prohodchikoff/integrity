def quoted_relation(db_type: str, namespace: str, model_name: str) -> str:
    if db_type == "postgresql":
        return f'"{namespace}"."{model_name}"'
    if db_type == "mysql":
        return f"`{namespace}`.`{model_name}`"
    raise ValueError(f"Unsupported db_type for relation quoting: {db_type!r}")
