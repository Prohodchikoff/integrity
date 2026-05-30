import re

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b("
    r"DROP|DELETE|INSERT|UPDATE|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"EXEC|EXECUTE|MERGE|CALL|COPY|LOAD|ATTACH|DETACH|VACUUM|PRAGMA"
    r")\b",
    re.IGNORECASE,
)


def validate_view_sql(sql: str) -> None:
    """Ensure compiled model SQL is a single SELECT suitable for CREATE VIEW."""
    normalized = sql.strip().rstrip(";").strip()
    if not normalized:
        raise ValueError("Model SQL is empty")

    if ";" in normalized:
        raise ValueError(
            "Model SQL must be a single statement; semicolons are not allowed"
        )

    if not re.search(r"\bSELECT\b", normalized, re.IGNORECASE):
        raise ValueError("Model SQL must be a SELECT statement")

    match = _FORBIDDEN_KEYWORDS.search(normalized)
    if match:
        raise ValueError(
            f"Model SQL contains forbidden keyword {match.group(0)!r}; "
            "only read-only SELECT bodies are allowed"
        )
