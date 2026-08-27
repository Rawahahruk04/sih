"""Live-demo mode: the capture-slot trap, and the demo scope itself.

The bug this file exists to pin: production correctly excludes any row
captured outside a narrow window around the fixed daily index slot (06:30 IST
+/- 45min) — a drifting capture time is collection noise, not inflation. A
live demo runs whenever the stage slot is, which is essentially never inside
that window. Without an explicit override, a demo's own live rows are
silently re-excluded by the very discipline that makes the production system
honest, and the "watch the data_mode banner shift" beat simply never happens
— while every earlier step (the rows print, they land in SQLite) looks like
it worked.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pandas as pd
import pytest

from aipi.basket import SAMPLE_ROUTES
from aipi.demo_config import DEMO_ROUTE_CODES, DEMO_ROUTES, DEMO_WINDOWS
from aipi.index.aggregate import expenditure_weights
from aipi.store import build_snapshot


def _off_slot_row(*, data_mode: str = "real") -> dict:
    """A row captured at an arbitrary "demo o'clock", not the 06:30 IST slot."""
    now = datetime.now(UTC)
    return {
        "capture_ts": now,
        "capture_date": now.date(),
        "travel_date": now.date() + timedelta(days=7),
        "advance_days": 7,
        "origin": "DEL",
        "destination": "BOM",
        "carrier": "6E",
        "flight_no": "6E-204",
        "fare_brand": "SAVER",
        "booking_class": "V",
        "cabin": "ECONOMY",
        "stops": 0,
        "is_codeshare": False,
        "base_fare": 4500.0,
        "taxes": 700.0,
        "udf_fee": 236.0,
        "convenience_fee": 0.0,
        "fees": 0.0,
        "total_fare": 5436.0,
        "currency": "INR",
        "source": "duffel",
        "data_mode": data_mode,
        "is_soldout": False,
    }


@pytest.fixture
def tiny_baseline() -> pd.DataFrame:
    from aipi.collectors.synthetic import SyntheticConfig, generate

    cfg = SyntheticConfig(start=date(2026, 6, 1), n_days=5, seed=1)
    return generate(cfg)


def _weights(routes) -> dict[str, float]:
    return expenditure_weights(
        {r.route_code: 100_000.0 for r in routes},
        {r.route_code: 5_000.0 for r in routes},
    )


def test_off_slot_row_is_dropped_by_default(tiny_baseline: pd.DataFrame) -> None:
    """The production default. This must NOT change — it is what protects the
    real index from capture-time drift being counted as inflation."""
    combined = pd.concat(
        [tiny_baseline, pd.DataFrame([_off_slot_row()])], ignore_index=True
    )
    snap = build_snapshot(combined, route_weights=_weights(SAMPLE_ROUTES))
    assert snap.report.data_mode_breakdown.get("real", 0) == 0


def test_enforce_slot_false_admits_the_live_row(tiny_baseline: pd.DataFrame) -> None:
    """The fix: with enforce_slot=False, the same row survives to the index."""
    combined = pd.concat(
        [tiny_baseline, pd.DataFrame([_off_slot_row()])], ignore_index=True
    )
    snap = build_snapshot(
        combined, route_weights=_weights(SAMPLE_ROUTES), enforce_slot=False
    )
    assert snap.report.data_mode_breakdown.get("real", 0) == 1


def test_api_bootstrap_disables_enforcement_only_for_the_blend(
    monkeypatch: pytest.MonkeyPatch, tmp_path, tiny_baseline: pd.DataFrame
) -> None:
    """Regression test for the actual bug: the API's demo bootstrap must pass
    enforce_slot=False when (and only when) loading a live-demo blend."""
    import aipi.api.deps as deps

    blend = pd.concat(
        [tiny_baseline, pd.DataFrame([_off_slot_row()])], ignore_index=True
    )
    blend_path = tmp_path / "blended_raw.parquet"
    blend.to_parquet(blend_path, index=False)

    monkeypatch.setattr(deps, "LIVE_DEMO_BLEND_PATH", str(blend_path))
    deps._store = None
    try:
        store = deps.get_store()
        assert store.data_mode_summary()["counts"].get("real", 0) == 1, (
            "the live row was re-excluded on reload — the exact bug this test "
            "guards against"
        )
    finally:
        deps._store = None


# --- demo scope --------------------------------------------------------


def test_demo_scope_is_a_subset_of_the_production_basket() -> None:
    basket_codes = {r.route_code for r in SAMPLE_ROUTES}
    assert set(DEMO_ROUTE_CODES) <= basket_codes


def test_demo_scope_is_smaller_than_production() -> None:
    """The whole point: fewer routes/windows than the full system, on purpose."""
    from aipi.basket import ADVANCE_WINDOWS, SAMPLE_ROUTES

    assert len(DEMO_ROUTES) < len(SAMPLE_ROUTES)
    assert len(DEMO_WINDOWS) < len(ADVANCE_WINDOWS)


def test_demo_windows_are_within_the_mandated_set() -> None:
    from aipi.basket import ADVANCE_WINDOWS

    assert set(DEMO_WINDOWS) <= set(ADVANCE_WINDOWS)
