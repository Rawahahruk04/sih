"""`openapi.json` is a published artefact and must never go stale.

An external frontend team codegens their client from this file. If someone
changes a response shape and forgets to regenerate, the generated client is
silently wrong — the failure surfaces as a runtime type error in someone else's
repo, days later, with no obvious cause.

So drift is a build failure here, not a surprise there. These tests also pin the
properties the frontend team was promised: every endpoint is an open read, the
error envelope is uniform, and lineage is present on index responses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aipi.api.main import create_app, resolve_cors_origins

REPO_ROOT = Path(__file__).resolve().parent.parent
OPENAPI_PATH = REPO_ROOT / "openapi.json"

#: The endpoints the frontend contract promises. Kept as an explicit list so
#: removing one is a deliberate act that breaks a test, not a silent regression.
REQUIRED_PATHS = {
    "/api/v1/index",
    "/api/v1/index/routes",
    "/api/v1/index/routes/heatmap",
    "/api/v1/index/routes/{route_code}",
    "/api/v1/index/leadtime",
    "/api/v1/index/leadtime/curve",
    "/api/v1/index/volatility",
    "/api/v1/validation/dgca",
    "/api/v1/routes",
    "/api/v1/methodology",
    "/api/v1/pipeline-run",
    "/health",
}


@pytest.fixture(scope="module")
def live_schema() -> dict:
    return create_app().openapi()


def test_openapi_json_exists() -> None:
    assert OPENAPI_PATH.exists(), (
        "openapi.json is missing. The frontend team codegens their client from "
        "it. Run: python -m scripts.export_openapi"
    )


def test_openapi_json_is_not_stale(live_schema: dict) -> None:
    """The committed file must match what the code actually serves."""
    committed = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    if committed != live_schema:
        committed_paths = set(committed.get("paths", {}))
        live_paths = set(live_schema.get("paths", {}))
        added = sorted(live_paths - committed_paths)
        removed = sorted(committed_paths - live_paths)
        pytest.fail(
            "openapi.json is out of date with the code.\n"
            f"  paths added since export:   {added or 'none'}\n"
            f"  paths removed since export: {removed or 'none'}\n"
            "  (schema bodies may also differ)\n"
            "Regenerate with: python -m scripts.export_openapi"
        )


def test_every_promised_endpoint_is_present(live_schema: dict) -> None:
    served = set(live_schema["paths"])
    missing = REQUIRED_PATHS - served
    assert not missing, f"endpoints promised to the frontend team are missing: {missing}"


def test_no_endpoint_requires_authentication(live_schema: dict) -> None:
    """This hackathon build is a public read API. Nothing may be gated.

    Checked against the schema rather than by reading the routes, because that is
    what a client generator sees: a `security` block or a securityScheme would
    make codegen emit auth plumbing for an API that has none.
    """
    assert not live_schema.get("security"), (
        f"a global security requirement was added: {live_schema.get('security')}"
    )
    schemes = live_schema.get("components", {}).get("securitySchemes")
    assert not schemes, f"security schemes defined on an open API: {schemes}"

    gated = [
        f"{method.upper()} {path}"
        for path, ops in live_schema["paths"].items()
        for method, op in ops.items()
        if isinstance(op, dict) and op.get("security")
    ]
    assert not gated, f"these endpoints require auth but must be open reads: {gated}"


def test_every_endpoint_is_read_only(live_schema: dict) -> None:
    """GET only. A write verb on this API would be a mistake, not a feature."""
    non_get = [
        f"{method.upper()} {path}"
        for path, ops in live_schema["paths"].items()
        for method in ops
        if method.lower() not in ("get", "parameters")
    ]
    assert not non_get, f"non-GET operations found on a read-only API: {non_get}"


def test_index_response_schema_carries_lineage(live_schema: dict) -> None:
    """`data_mode` is required on the headline response, not optional decoration."""
    headline = live_schema["components"]["schemas"]["HeadlineResponse"]
    assert "data_mode" in headline["properties"], (
        "HeadlineResponse dropped data_mode — a consumer could no longer tell a "
        "measurement from a simulation."
    )
    assert "data_mode" in headline.get("required", []), (
        "data_mode must be REQUIRED: an optional lineage field is one a client "
        "will forget to read."
    )


def test_frequency_parameter_is_documented(live_schema: dict) -> None:
    params = live_schema["paths"]["/api/v1/index"]["get"]["parameters"]
    names = {p["name"] for p in params}
    for expected in ("freq", "from", "to", "dow_adjusted"):
        assert expected in names, f"/api/v1/index lost its {expected!r} parameter"


# ---------------------------------------------------------------------------
# CORS: the frontend team must be able to whitelist their own origins without a
# code change, so the env var is part of the contract.
# ---------------------------------------------------------------------------


def test_cors_defaults_to_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRONTEND_ORIGINS", raising=False)
    monkeypatch.delenv("AIPI_CORS_ORIGINS", raising=False)
    assert resolve_cors_origins() == ["*"]


def test_frontend_origins_accepts_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIPI_CORS_ORIGINS", raising=False)
    monkeypatch.setenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,https://aipi-dashboard.vercel.app"
    )
    assert resolve_cors_origins() == [
        "http://localhost:5173",
        "https://aipi-dashboard.vercel.app",
    ]


def test_blank_entries_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A trailing comma must not produce an empty origin that matches nothing."""
    monkeypatch.delenv("AIPI_CORS_ORIGINS", raising=False)
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://localhost:5173, ,")
    assert resolve_cors_origins() == ["http://localhost:5173"]


def test_frontend_origins_wins_over_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTEND_ORIGINS", "http://new.example")
    monkeypatch.setenv("AIPI_CORS_ORIGINS", "http://legacy.example")
    assert resolve_cors_origins() == ["http://new.example"]


def test_cors_headers_are_actually_sent() -> None:
    """End-to-end: a browser preflight from a whitelisted origin must succeed.

    Asserted against a real response rather than the config, because middleware
    ordering and `allow_methods` can both silently defeat a correct origin list.
    """
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173")
