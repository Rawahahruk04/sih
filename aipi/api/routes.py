"""API routes. Thin handlers over the store; no computation here."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from aipi import __version__
from aipi.api.deps import get_store
from aipi.api.schemas import (
    HeadlineResponse,
    HealthResponse,
    LeadtimeCurveResponse,
    LeadtimeIndexResponse,
    PipelineRunModel,
    RouteResponse,
    RoutesResponse,
)
from aipi.store import IndexStore, SeriesNotFound

router = APIRouter()


def _require_data(store: IndexStore) -> None:
    if not store.available():
        # 503, not 404: the endpoint exists, the data is not ready. A collector that
        # has produced nothing is an operational state, not a client error.
        raise HTTPException(status_code=503, detail="No index data available yet.")


@router.get("/health", response_model=HealthResponse, tags=["ops"])
def health(store: IndexStore = Depends(get_store)) -> HealthResponse:
    latest = store.latest_index_date() if store.available() else None
    return HealthResponse(
        status="ok",
        data_available=store.available(),
        latest_index_date=latest.isoformat() if latest else None,
        code_version=__version__,
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
    store: IndexStore = Depends(get_store),
) -> dict:
    _require_data(store)
    return {
        "series": "headline_dow_adjusted" if dow_adjusted else "headline",
        "dow_adjusted": dow_adjusted,
        "base_period": store.methodology()["base_period"],
        "pipeline_run": store.pipeline_run(),
        "points": store.headline(dow_adjusted=dow_adjusted),
        "count": len(store.headline(dow_adjusted=dow_adjusted)),
    }


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
        "note": "Index per advance window (base period = 100). Inflation by window, not fare level.",
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
