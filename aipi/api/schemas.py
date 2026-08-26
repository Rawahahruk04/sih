"""Response schemas. Every published value carries the accompaniment that makes it
a statistic rather than a number: n_obs and coverage_pct are required on the series
points, not optional decoration.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PipelineRunModel(BaseModel):
    run_id: str
    code_version: str
    git_sha: str
    config_hash: str
    input_row_count: int
    index_eligible_rows: int
    created_at: str


class BasePeriod(BaseModel):
    start: str | None
    end: str | None
    n_days: int


class IndexPoint(BaseModel):
    date: str
    value: float
    n_obs: int = Field(..., description="Index-eligible observations behind this point.")
    coverage_pct: float = Field(..., description="Share of the expected sample present.")
    matched_n: int | None = Field(
        None, description="Matched pairs entering the elementary aggregate (headline only)."
    )


class HeadlineResponse(BaseModel):
    series: str
    dow_adjusted: bool
    base_period: BasePeriod
    pipeline_run: PipelineRunModel
    count: int
    points: list[IndexPoint]


class RouteSummary(BaseModel):
    route_code: str
    display_name: str
    weight: float
    latest_date: str
    latest_value: float


class RoutesResponse(BaseModel):
    pipeline_run: PipelineRunModel
    count: int
    routes: list[RouteSummary]


class RouteResponse(BaseModel):
    route_code: str
    display_name: str
    weight: float
    pipeline_run: PipelineRunModel
    count: int
    points: list[IndexPoint]


class LeadtimeWindow(BaseModel):
    advance_days: int
    points: list[IndexPoint]


class LeadtimeIndexResponse(BaseModel):
    note: str
    pipeline_run: PipelineRunModel
    windows: list[LeadtimeWindow]


class LeadtimeCurvePoint(BaseModel):
    advance_days: int
    relative_level: float


class LeadtimeCurveResponse(BaseModel):
    as_of: str | None
    reference_window: int | None
    note: str | None = None
    curve: list[LeadtimeCurvePoint]


class HealthResponse(BaseModel):
    status: str
    data_available: bool
    latest_index_date: str | None
    code_version: str
