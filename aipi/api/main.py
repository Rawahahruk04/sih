"""App factory. Wires routes, CORS, startup warm-up, and the static dashboard."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from aipi import __version__
from aipi.api.deps import warm_store
from aipi.api.routes import router

log = logging.getLogger(__name__)

_DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"

#: Origins allowed to call this API from a browser.
#:
#: `FRONTEND_ORIGINS` is the documented name — the frontend team sets their local
#: dev URL and their deployed URL here without touching code. `*` (the default)
#: is right for a public, unauthenticated read API and for local development;
#: narrow it for anything else.
#:
#: `AIPI_CORS_ORIGINS` is accepted as a fallback so an already-written .env does
#: not silently stop working, but `FRONTEND_ORIGINS` wins where both are set.
ORIGINS_ENV_VAR = "FRONTEND_ORIGINS"
ORIGINS_ENV_VAR_LEGACY = "AIPI_CORS_ORIGINS"


def resolve_cors_origins() -> list[str]:
    """Read the allowed-origins list from the environment."""
    raw = os.getenv(ORIGINS_ENV_VAR)
    if raw is None:
        raw = os.getenv(ORIGINS_ENV_VAR_LEGACY)
        if raw is not None:
            log.warning(
                "%s is deprecated; use %s", ORIGINS_ENV_VAR_LEGACY, ORIGINS_ENV_VAR
            )
    raw = (raw or "*").strip()
    if raw == "*":
        return ["*"]
    # Drop empties so a trailing comma cannot produce an origin of "" that
    # matches nothing and is invisible in the config.
    return [o.strip() for o in raw.split(",") if o.strip()]

DESCRIPTION = """
Real-Time Airfare Price Index for India (AIPI) — SIH 2026 PS 26056 (MoSPI).

Every published value carries `n_obs` and `coverage_pct`, and every response carries
the `pipeline_run` provenance stamp (code version, git SHA, methodology config hash,
input row count) needed to reproduce it.

**Methodology proof of concept. Not an official government statistic.**
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build the index before the app serves its first request.

    Doing this lazily meant the first caller paid ~11 seconds and the container
    reported healthy before it could answer. Warming here means `docker compose
    up` is genuinely the whole onboarding step: when the health check passes,
    every endpoint is already populated.
    """
    warm_store()
    log.info("store warm; API ready")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AIPI — Airfare Price Index for India",
        version=__version__,
        description=DESCRIPTION,
        lifespan=lifespan,
    )

    # The dashboard is a static single-page app served same-origin; CORS is opened
    # so the API can also be called from a separate frontend dev server.
    # Configurable because "permissive by default" is right for a public read API
    # and for local development, and wrong for anything holding credentials.
    #
    # Note: `allow_credentials` is deliberately NOT set. With `allow_origins=["*"]`
    # browsers reject credentialed requests anyway, and this API has no auth and
    # no cookies to send — see the module docstring on FRONTEND_ORIGINS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolve_cors_origins(),
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # One error shape for every failure, so a client writes one parser rather than
    # branching on FastAPI's default `detail` vs our own envelope.
    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        codes = {
            404: "not_found",
            422: "invalid_request",
            503: "data_unavailable",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": codes.get(exc.status_code, "error"),
                "detail": str(exc.detail),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_request", "detail": str(exc.errors())},
        )

    app.include_router(router)

    if _DASHBOARD_DIR.is_dir():
        app.mount(
            "/dashboard",
            StaticFiles(directory=str(_DASHBOARD_DIR), html=True),
            name="dashboard",
        )

        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(url="/dashboard/")
    else:

        @app.get("/", include_in_schema=False)
        def _root() -> RedirectResponse:
            return RedirectResponse(url="/docs")

    return app


app = create_app()
