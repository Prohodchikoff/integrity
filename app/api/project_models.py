from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectPathBody(BaseModel):
    project_name: str = Field(
        ...,
        description="Project name from app/config/environments.yaml -> projects.*",
    )


class ProjectRunBody(ProjectPathBody):
    env: str | None = Field(
        default=None,
        description="Environment profile from app/config/environments.yaml (if omitted, project's default_environment is used).",
    )


class ParsedModelInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    path: str
    refs: list[str]


class ProjectParseResponse(BaseModel):
    project_name: str
    order: list[str]
    models: list[ParsedModelInfoResponse]


class TestSummaryResponse(BaseModel):
    total: int
    passed: int
    failed: int


class TestResultItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    test_id: str
    model: str
    column: str
    type: str
    ok: bool
    fail_count: int
    error: str | None = None


class ProjectTestsResponse(BaseModel):
    project_name: str
    summary: TestSummaryResponse
    tests: list[TestResultItemResponse]


class RunModelResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    ok: bool
    error: str | None = None
    elapsed_ms: float | None = None


class ProjectRunResponse(BaseModel):
    project_name: str
    order: list[str]
    models: list[RunModelResultResponse]


class ProjectJobAcceptedResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "succeeded", "failed"]


class ProjectJobStatusResponse(BaseModel):
    job_id: str
    kind: Literal["run", "test"]
    status: Literal["queued", "running", "succeeded", "failed"]
    project_name: str
    env: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    progress_done: int = 0
    progress_total: int | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
