from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    model_config = ConfigDict(validate_assignment=True)

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
    result: ProjectRunResponse | ProjectTestsResponse | None = None
    error: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_result_by_kind(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        kind = data.get("kind")
        result = data.get("result")
        if result is None or not isinstance(result, dict) or kind not in {"run", "test"}:
            return data
        if kind == "run":
            data["result"] = ProjectRunResponse.model_validate(result)
        else:
            data["result"] = ProjectTestsResponse.model_validate(result)
        return data

    @model_validator(mode="after")
    def result_matches_kind(self) -> Self:
        if self.result is None:
            return self
        if self.kind == "run" and not isinstance(self.result, ProjectRunResponse):
            raise ValueError("result must be ProjectRunResponse for run jobs")
        if self.kind == "test" and not isinstance(self.result, ProjectTestsResponse):
            raise ValueError("result must be ProjectTestsResponse for test jobs")
        return self
