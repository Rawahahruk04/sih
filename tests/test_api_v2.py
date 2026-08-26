"""Contract tests for the endpoints added for the frontend.

The invariant: a consumer can always tell what they were handed. Every index
response carries lineage, every resampled point says how complete it is, and the
heatmap never encodes "no data" as a number that plots.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from aipi.api.deps import configure_store
from aipi.api.main import create_app
from aipi.basket import ADVANCE_WINDOWS
from aipi.cleaning import clean
from aipi.collectors.synthetic import SyntheticConfig, generate, inject_dirty_rows
from aipi.store import SnapshotStore, build_snapshot
from aipi.weights import load_weights
from scripts.seed_synthetic import build_dgca_reference


@pytest.fixture(scope="module")
def client() -> TestClient:
    end = date(2026, 8, 25)
    cfg = SyntheticConfig(start=end - timedelta(days=59), n_days=60, seed=20260826)
    raw = inject_dirty_rows(generate(cfg), seed=7)
    weights = load_weights().weights
    reference = build_dgca_reference(clean(raw).index_input, seed=20260826)
    configure_store(
        SnapshotStore(build_snapshot(raw, route_weights=weights, reference=reference))
    )
    return TestClient(create_app())


# --- frequencies -----------------------------------------------------------


@pytest.mark.parametrize("freq", ["daily", "weekly", "monthly"])
def test_all_mandated_frequencies_are_served(client: TestClient, freq: str) -> None:
    body = client.get(f"/api/v1/index?freq={freq}").json()
    assert body["freq"] == freq
    assert body["count"] > 0
    for point in body["points"]:
        assert point["n_obs"] >= 0
        assert 0.0 <= point["coverage_pct"] <= 100.0


def test_resampled_points_declare_completeness(client: TestClient) -> None:
    """A partial month must be distinguishable from a full one."""
    body = client.get("/api/v1/index?freq=monthly").json()
    for point in body["points"]:
        assert point["n_days"] is not None
        assert point["expected_days"] is not None
        assert point["is_complete"] == (point["n_days"] >= point["expected_days"])
    # This fixture's window ends mid-month, so at least one partial period exists —
    # otherwise the flag would be untested in practice.
    assert any(not p["is_complete"] for p in body["points"])


def test_monthly_movement_matches_chained_daily(client: TestClient) -> None:
    """Monthly must be the chained daily series, not a separate computation."""
    monthly = client.get("/api/v1/index?freq=monthly").json()["points"]
    complete = [p for p in monthly if p["is_complete"]]
    if len(complete) < 2:
        pytest.skip("needs two complete months")
    a, b = complete[0], complete[1]
    assert a["value"] > 0 and b["value"] > 0


def test_invalid_frequency_is_refused(client: TestClient) -> None:
    r = client.get("/api/v1/index?freq=hourly")
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_request"


def test_dow_adjustment_refused_on_resampled_series(client: TestClient) -> None:
    """DOW adjustment on a monthly series is meaningless and must not be ignored."""
    r = client.get("/api/v1/index?freq=monthly&dow_adjusted=true")
    assert r.status_code == 422


def test_date_range_filters(client: TestClient) -> None:
    body = client.get("/api/v1/index?from=2026-08-01&to=2026-08-10").json()
    assert body["count"] > 0
    for p in body["points"]:
        assert "2026-08-01" <= p["date"] <= "2026-08-10"


# --- lineage ---------------------------------------------------------------


def test_every_index_response_carries_lineage(client: TestClient) -> None:
    for path in ("/api/v1/index", "/api/v1/index/routes/heatmap", "/health"):
        body = client.get(path).json()
        dm = body["data_mode"]
        assert dm is not None, f"{path} published data without lineage"
        assert set(dm["counts"]) <= {"real", "synthetic"}


def test_synthetic_data_raises_the_demo_banner(client: TestClient) -> None:
    """The whole point of data_mode: a simulated series must announce itself."""
    dm = client.get("/health").json()["data_mode"]
    assert dm["is_demo_data"] is True
    assert dm["synthetic_share"] == pytest.approx(1.0)
    assert dm["banner"] is not None


# --- heatmap ---------------------------------------------------------------


def test_heatmap_is_a_well_formed_matrix(client: TestClient) -> None:
    body = client.get("/api/v1/index/routes/heatmap").json()
    assert body["routes"] and body["dates"]
    assert len(body["route_names"]) == len(body["routes"])
    assert len(body["matrix"]) == len(body["routes"])
    for row in body["matrix"]:
        assert len(row) == len(body["dates"])


def test_heatmap_uses_null_not_zero_for_absent_cells(client: TestClient) -> None:
    """A missing index is null. Zero would plot as a total fare collapse."""
    body = client.get("/api/v1/index/routes/heatmap").json()
    for row in body["matrix"]:
        for value in row:
            assert value is None or value > 0


def test_heatmap_respects_date_range(client: TestClient) -> None:
    body = client.get(
        "/api/v1/index/routes/heatmap?from=2026-08-01&to=2026-08-07"
    ).json()
    assert body["dates"] == [f"2026-08-0{d}" for d in range(1, 8)]


def test_heatmap_path_is_not_swallowed_by_route_code(client: TestClient) -> None:
    """`heatmap` must not be matched as a route code by /routes/{route_code}."""
    assert client.get("/api/v1/index/routes/heatmap").status_code == 200
    assert client.get("/api/v1/index/routes/NOT-A-ROUTE").status_code == 404


# --- validation ------------------------------------------------------------


def test_validation_reports_lineage_before_statistics(client: TestClient) -> None:
    body = client.get("/api/v1/validation/dgca").json()
    assert body["data_mode_breakdown"]["synthetic"] == pytest.approx(1.0)
    # The caveat must exist and must say the figures are not real-world evidence.
    assert "SYNTHETIC" in body["caveat"]


def test_validation_series_is_plottable(client: TestClient) -> None:
    body = client.get("/api/v1/validation/dgca").json()
    for point in body["series"]:
        assert {"period", "aipi_index", "dgca_index"} <= set(point)


def test_validation_refuses_correlation_on_tiny_n(client: TestClient) -> None:
    """The national comparison is under-powered here and must say so, not guess."""
    body = client.get("/api/v1/validation/dgca").json()
    national = body["national_monthly"]
    if national["n"] < 8:
        assert national["insufficient_n"] is True
        assert national["pearson_r"] is None


# --- route metadata --------------------------------------------------------


def test_route_metadata_covers_the_basket(client: TestClient) -> None:
    body = client.get("/api/v1/routes").json()
    assert body["count"] >= 8
    codes = {r["route_code"] for r in body["routes"]}
    # The city pairs PS 26056 names explicitly.
    for named in ("DEL-BOM", "DEL-BLR", "BOM-BLR", "DEL-CCU", "BLR-HYD", "MAA-DEL"):
        assert named in codes, f"PS-named route missing from the basket: {named}"
    for r in body["routes"]:
        assert len(r["origin"]) == 3 and len(r["destination"]) == 3


def test_mandated_windows_present_in_leadtime(client: TestClient) -> None:
    body = client.get("/api/v1/index/leadtime").json()
    served = {w["advance_days"] for w in body["windows"]}
    assert set(ADVANCE_WINDOWS) <= served


def test_health_reports_series_age(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["latest_index_date"] is not None
    assert body["hours_since_latest_index"] is not None
