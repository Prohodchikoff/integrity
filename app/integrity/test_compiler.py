def build_not_null_sql(relation:str, column:str)-> str:
    stmt = f"""
    SELECT * FROM {relation} WHERE {column} IS NULL
    """.strip()

    return stmt

