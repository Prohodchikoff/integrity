from pydantic import BaseModel, Field, field_validator


class SourceConfig(BaseModel):
    name: str
    schema: str | None = Field(
        default=None,
        description="Schema/database namespace for tables; defaults to project execution namespace.",
    )
    tables: list[str] = Field(default_factory=list)

    @field_validator("tables", mode="after")
    @classmethod
    def _normalize_tables(cls, tables: list[str]) -> list[str]:
        if not tables:
            raise ValueError("Each source must declare at least one table")
        seen: set[str] = set()
        out: list[str] = []
        for raw in tables:
            name = raw.strip()
            if not name:
                raise ValueError("Source table names cannot be empty")
            if name in seen:
                raise ValueError(f"Duplicate source table name {name!r}")
            seen.add(name)
            out.append(name)
        return out

    def resolve_table(self, table_name: str) -> str:
        if table_name not in self.tables:
            raise ValueError(
                f"Table {table_name!r} is not declared on source {self.name!r}. "
                f"Known tables: {', '.join(sorted(self.tables))}"
            )
        return table_name


def source_index(sources: list[SourceConfig]) -> dict[str, SourceConfig]:
    index: dict[str, SourceConfig] = {}
    for src in sources:
        if src.name in index:
            raise ValueError(f"Duplicate source name {src.name!r}")
        index[src.name] = src
    return index
