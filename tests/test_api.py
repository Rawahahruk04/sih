"""API contract tests.

The invariant these exist to guard: the API never publishes a bare value. Every
series point carries n_obs and coverage_pct, every response carries the pipeline_run
stamp, and /methodology exposes the fingerprint and the cleaning row-accounting. If a
future change drops any of that, a statistician downstream loses the ability to tell
signal from a collection gap — so these are contract tests, not smoke tests.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from aipi.api.deps import configure_store
from aipi.api.main import create_app
from aipi.collectors.synthetic import SyntheticConfig, generate
from aipi.index.aggregate import expenditure_weights
from aipi.collectors.synthetic import demo_base_fares, demo_passengers
from aipi.store import SnapshotStore, build_snapshot


@pytest.fixture(scope="module")
def client() -> TestClient:
    # A short, fully-deterministic run so the suite stays fast. build_snapshot drives
    # the real clean -> index -> provenance path, so this exercises the whole stack.
    cfg = SyntheticConfig(start=date(2026, 6, 1), n_days=40, seed=20260826)
    raw = generate(cfg)
    weights = expenditure_weights(demo_passengers(), demo_base_fares())
    snap = build_snapshot(
        raw, route_weights=weights, generated_at=datetime(2026, 8, 26, tzinfo=timezone.utc)
    )
    configure_store(SnapshotStore(snap))
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["data_available"] is True
    assert body["latest_index_date"]


def test_headline_every_point_has_n_obs_and_coverage(client: TestClient) -> None:
    r = client.get("/api/v1/index")
    assert r.status_code == 200
    body = r.json()
    assert body["series"] == "headline"
    assert body["count"] == len(body["points"])
    assert body["points"], "headline series is empty"
    for p in body["points"]:
        assert "n_obs" in p and p["n_obs"] >= 0
        assert "coverage_pct" in p and 0.0 <= p["coverage_pct"] <= 100.0
        assert p["value"] > 0
    # The base is 100 by construction: the first published point is near it.
    assert abs(body["points"][0]["value"] - 100.0) < 15.0


def test_headline_dow_adjusted_switch(client: TestClient) -> None:
    raw = client.get("/api/v1/index").json()
    adj = client.get("/api/v1/index?dow_adjusted=true").json()
    assert adj["series"] == "headline_dow_adjusted"
    assert adj["dow_adjusted"] is True
    assert len(adj["points"]) == len(raw["points"])


def test_pipeline_run_stamp_present(client: TestClient) -> None:
    run = client.get("/api/v1/index").json()["pipeline_run"]
    assert run["run_id"]
    assert len(run["config_hash"]) == 64
    assert run["input_row_count"] > run["index_eligible_rows"] >= 0


def test_routes_sorted_by_weight(client: TestClient) -> None:
    body = client.get("/api/v1/index/routes").json()
    weights = [r["weight"] for r in body["routes"]]
    assert weights == sorted(weights, reverse=True)
    assert body["count"] == len(body["routes"])


def test_unknown_route_404(client: TestClient) -> None:
    assert client.get("/api/v1/index/routes/ZZZ-XXX").status_code == 404


def test_known_route_points(client: TestClient) -> None:
    code = client.get("/api/v1/index/routes").json()["routes"][0]["route_code"]
    body = client.get(f"/api/v1/index/routes/{code}").json()
    assert body["route_code"] == code
    assert body["points"]
    for p in body["points"]:
        assert p["n_obs"] >= 0
        assert 0.0 <= p["coverage_pct"] <= 100.0


def test_methodology_exposes_fingerprint_and_cleaning(client: TestClient) -> None:
    m = client.get("/api/v1/methodology").json()
    assert m["fingerprint"]["basket"]["brand_family"] == "SAVER"
    assert m["base_period"]["n_days"] >= 1
    assert m["cleaning"]["rows_in"] > 0
    assert "Jevons" in m["index_number"]["elementary_aggregate"]
    assert "GEKS" in m["index_number"]["multilateral"]


def test_leadtime_price_curve_is_monotone(client: TestClient) -> None:
    body = client.get("/api/v1/index/leadtime/curve").json()
    curve = body["curve"]
    assert body["reference_window"] == 14
    levels = [pt["relative_level"] for pt in curve]
    # Fares must fall as booking moves earlier. This is the object that should be
    # monotone (unlike the per-window inflation index).
    assert levels == sorted(levels, reverse=True)
    ref = next(pt["relative_level"] for pt in curve if pt["advance_days"] == 14)
    assert abs(ref - 100.0) < 1e-6


def test_leadtime_index_is_not_the_curve(client: TestClient) -> None:
    body = client.get("/api/v1/index/leadtime").json()
    assert body["windows"]
    for w in body["windows"]:
        for p in w["points"]:
            assert p["n_obs"] >= 0
            assert 0.0 <= p["coverage_pct"] <= 100.0


def test_volatility_carries_sampling_error(client: TestClient) -> None:
    v = client.get("/api/v1/index/volatility").json()
    assert "daily" in v
    assert v["daily"]["suspiciously_flat"] is False  # synthetic data moves
    se = v.get("sampling_error", {})
    assert "curve" in se and se["curve"], "sampling-error curve missing"
