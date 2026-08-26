"""App factory. Wires routes, CORS, and (if present) the static dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from aipi import __version__
from aipi.api.routes import router

_DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"

DESCRIPTION = """
Real-Time Airfare Price Index for India (AIPI) — SIH 2026 PS 26056 (MoSPI).

Every published value carries `n_obs` and `coverage_pct`, and every response carries
the `pipeline_run` provenance stamp (code version, git SHA, methodology config hash,
input row count) needed to reproduce it.

**Methodology proof of concept. Not an official government statistic.**
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title="AIPI — Airfare Price Index for India",
        version=__version__,
        description=DESCRIPTION,
    )

    # The dashboard is a static single-page app served same-origin; CORS is opened
    # only so the API can also be explored from a separate dev server if desired.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(router)

    if _DASHBOARD_DIR.is_dir():
        app.mount("/dashboard", StaticFiles(directory=str(_DASHBOARD_DIR), html=True), name="dashboard")

        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(url="/dashboard/")
    else:

        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(url="/docs")

    return app


app = create_app()
