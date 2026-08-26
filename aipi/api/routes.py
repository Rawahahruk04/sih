"""API routes. Thin handlers over the store; no computation here."""

from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from aipi import __version__
from aipi.api.deps import get_store
from aipi.api.schemas import (
    HeadlineResponse,
    HealthResponse,
    HeatmapResponse,
    LeadtimeCurveResponse,
    LeadtimeIndexResponse,
    PipelineRunModel,
    RouteMetadataResponse,
    RouteResponse,
    RoutesResponse,
)
from aipi.store import IndexStore, SeriesNotFound

router = APIRouter()

VALID_FREQ = ("daily", "weekly", "monthly")


def _require_data(store: IndexStore) -> None:
    if not store.available():
        # 503, not 404: the endpoint exists, the data is not ready. A collector that
        # has produced nothing is an operational state, not a client error.
        raise HTTPException(status_code=503, detail="No index data available yet.")


@router.get("/health", response_model=HealthResponse, tags=["ops"])
def health(store: IndexStore = Depends(get_store)) -> HealthResponse:
    latest = store.latest_index_date() if store.available() else None
    age_hours: float | None = None
    if latest is not None:
        delta = datetime.now(UTC).date() - latest
        age_hours = round(delta.days * 24.0, 2)
    return HealthResponse(
        status="ok",
        data_available=store.available(),
        latest_index_date=latest.isoformat() if latest else None,
        code_version=__version__,
        data_mode=store.data_mode_summary() if store.available() else None,
        hours_since_latest_index=age_hours,
    )


@router.get("/api/v1/methodology", tags=["methodology"])
def methodology(store: IndexStore = Depends(get_store)) -> dict:
    """The basket, the index-number formulae, the methodology fingerprint, and the
    full cleaning row-accounting. Publishing this is what separates a statistic from
    a number."""
    _require_data(store)
    return store.methodology()


@router.get("/api/v1/pipeline-run", response_model=PipelineRunModel, tags=["methodology"])
def pipeline_run(store: IndexStore = Depends(get_store)) -> dict:
    _require_data(store)
    return store.pipeline_run()


@router.get("/api/v1/index", response_model=HeadlineResponse, tags=["index"])
def headline(
    dow_adjusted: bool = Query(False, description="Return the day-of-week-adjusted series."),
    freq: str = Query("daily", description="daily | weekly | monthly"),
    date_from: date | None = Query(None, alias="from", description="Inclusive start date."),
    date_to: date | None = Query(None, alias="to", description="Inclusive end date."),
    store: IndexStore = Depends(get_store),
) -> dict:
    _require_data(store)
    if freq not in VALID_FREQ:
        raise HTTPException(
            status_code=422,
            detail=f"freq must be one of {VALID_FREQ}, got {freq!r}",
        )
    if dow_adjusted and freq != "daily":
        # Day-of-week adjustment removes a WITHIN-week cycle. Applying it to a
        # weekly or monthly series is meaningless — the cycle is already averaged
        # out — so this is refused rather than silently ignored.
        raise HTTPException(
            status_code=422,
            detail=(
                "dow_adjusted applies only to freq=daily: a weekly or monthly "
                "series has already averaged the within-week cycle away."
            ),
        )

    points = store.headline(dow_adjusted=dow_adjusted, freq=freq)
    if date_from:
        points = [p for p in points if p["date"] >= date_from.isoformat()]
    if date_to:
        points = [p for p in points if p["date"] <= date_to.isoformat()]

    return {
        "series": "headline_dow_adjusted" if dow_adjusted else "headline",
        "freq": freq,
        "dow_adjusted": dow_adjusted,
        "base_period": store.methodology()["base_period"],
        "pipeline_run": store.pipeline_run(),
        "data_mode": store.data_mode_summary(),
        "points": points,
        "count": len(points),
    }


@router.get("/api/v1/routes", response_model=RouteMetadataResponse, tags=["reference"])
def route_metadata(store: IndexStore = Depends(get_store)) -> dict:
    """Route dimension for dropdowns and filters. Identity only, no series."""
    _require_data(store)
    routes = store.route_metadata()
    return {"count": len(routes), "routes": routes}


@router.get(
    "/api/v1/index/routes/heatmap", response_model=HeatmapResponse, tags=["index"]
)
def route_heatmap(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    store: IndexStore = Depends(get_store),
) -> dict:
    """Route x date matrix for the sector-wise heatmap.

    Declared BEFORE `/index/routes/{route_code}` so the literal path wins the
    route match — otherwise 'heatmap' is captured as a route code and returns 404.
    """
    _require_data(store)
    payload = store.route_heatmap(start=date_from, end=date_to)
    payload["data_mode"] = store.data_mode_summary()
    return payload


@router.get("/api/v1/validation/dgca", tags=["validation"])
def validation_dgca(store: IndexStore = Depends(get_store)) -> dict:
    """Back-test against the reference series, with lineage stated up front.

    Always returns 200 with an `available` flag rather than erroring when no
    reference is loaded: "no reference yet" is an ordinary operational state
    early in collection, not a client mistake, and the dashboard needs to render
    something either way.
    """
    _require_data(store)
    return store.validation()


@router.get("/api/v1/index/routes", response_model=RoutesResponse, tags=["index"])
def routes(store: IndexStore = Depends(get_store)) -> dict:
    _require_data(store)
    routes = store.list_routes()
    return {"pipeline_run": store.pipeline_run(), "count": len(routes), "routes": routes}


@router.get("/api/v1/index/routes/{route_code}", response_model=RouteResponse, tags=["index"])
def route(route_code: str, store: IndexStore = Depends(get_store)) -> dict:
    _require_data(store)
    try:
        points = store.route(route_code)
    except SeriesNotFound as exc:
        raise HTTPException(status_code=404, detail=f"Unknown route: {route_code}") from exc
    summary = next(
        (r for r in store.list_routes() if r["route_code"] == route_code), None
    )
    return {
        "route_code": route_code,
        "display_name": summary["display_name"] if summary else route_code,
        "weight": summary["weight"] if summary else 0.0,
        "pipeline_run": store.pipeline_run(),
        "points": points,
        "count": len(points),
    }


@router.get("/api/v1/index/leadtime", response_model=LeadtimeIndexResponse, tags=["index"])
def leadtime(store: IndexStore = Depends(get_store)) -> dict:
    """Index by advance-purchase window (base period = 100): how fast each window's
    fares are inflating. This is NOT the fare-level curve — see /leadtime/curve."""
    _require_data(store)
    idx = store.leadtime_index()
    return {
        "note": (
            "Index per advance window (base period = 100). "
            "Inflation by window, not fare level."
        ),
        "pipeline_run": store.pipeline_run(),
        "windows": [{"advance_days": w, "points": pts} for w, pts in idx.items()],
    }


@router.get(
    "/api/v1/index/leadtime/curve", response_model=LeadtimeCurveResponse, tags=["index"]
)
def leadtime_curve(
    as_of: date | None = Query(None, description="Curve as at this date; latest if omitted."),
    store: IndexStore = Depends(get_store),
) -> dict:
    """Relative fare LEVEL by advance window (14-day window = 100): how much more a
    last-minute booking costs than an advance one."""
    _require_data(store)
    return store.leadtime_price_curve(as_of=as_of)


@router.get("/api/v1/index/volatility", tags=["index"])
def volatility(store: IndexStore = Depends(get_store)) -> dict:
    """Daily and intraday fare volatility, plus the sparse-sampling measurement-error
    analysis: the evidence that daily collection is worth its cost."""
    _require_data(store)
    return store.volatility()
