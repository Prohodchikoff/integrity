import re
from collections.abc import Iterable

REF_PATTERN = re.compile(
    r"""\{\{\s*ref\s*\(\s*['\"](?P<name>[^'\"]+)['\"]\s*\)\s*\}\}""",
    re.IGNORECASE | re.DOTALL,
)


def extract_ref_names(sql: str) -> set[str]:
    return {m.group("name") for m in REF_PATTERN.finditer(sql)}


def validate_refs(model_name: str, refs: Iterable[str], known_models: set[str]) -> list[str]:
    errors: list[str] = []
    for r in refs:
        if r not in known_models:
            errors.append(
                f"Model {model_name!r} references unknown model {r!r} (ref must name another .sql model)."
            )
    return errors
