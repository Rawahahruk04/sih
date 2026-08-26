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
    n_days: int | None = Field(
        None,
        description=(
            "Daily observations aggregated into this point. Weekly/monthly only — "
            "a weekly point built from 3 days is not the same statistic as one "
            "built from 7."
        ),
    )
    expected_days: int | None = Field(
        None, description="Days a complete period would contain. Weekly/monthly only."
    )
    is_complete: bool | None = Field(
        None,
        description=(
            "False for a partially-observed period. Render these distinctly — a "
            "14-day month plotted beside a 31-day month is not comparable."
        ),
    )


class DataModeSummary(BaseModel):
    """Real-vs-synthetic lineage. Present on every index response by design.

    A consumer must never have to guess whether a series is a measurement or a
    simulation, so this travels with the data rather than living in a README.
    """

    counts: dict[str, int]
    total_rows: int
    real_share: float
    synthetic_share: float
    is_demo_data: bool
    banner: str | None = Field(
        None, description="Non-null when the dashboard must show a demo-data warning."
    )


class HeadlineResponse(BaseModel):
    series: str
    freq: str = Field("daily", description="daily | weekly | monthly")
    dow_adjusted: bool
    base_period: BasePeriod
    pipeline_run: PipelineRunModel
    data_mode: DataModeSummary
    count: int
    points: list[IndexPoint]


class RouteMetadata(BaseModel):
    route_code: str
    origin: str
    destination: str
    display_name: str
    weight: float
    in_index: bool


class RouteMetadataResponse(BaseModel):
    count: int
    routes: list[RouteMetadata]


class HeatmapResponse(BaseModel):
    """Route x date grid, pre-shaped so a heatmap component needs no reshaping."""

    routes: list[str]
    route_names: list[str]
    dates: list[str]
    matrix: list[list[float | None]] = Field(
        ..., description="matrix[i][j] = routes[i] on dates[j]; null = no index, NOT zero."
    )
    value_min: float | None
    value_max: float | None
    baseline: float
    note: str
    data_mode: DataModeSummary


class ValidationSeriesPoint(BaseModel):
    period: str
    aipi_index: float
    dgca_index: float


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
    data_mode: DataModeSummary | None = None
    hours_since_latest_index: float | None = Field(
        None,
        description=(
            "Age of the most recent index point. A stale series looks identical to "
            "a flat one on a chart, so the age is published rather than inferred."
        ),
    )


class ErrorResponse(BaseModel):
    """Uniform error envelope on every 4xx/5xx, so clients parse one shape."""

    error: str = Field(..., description="Short machine-readable code.")
    detail: str = Field(..., description="Human-readable explanation.")
