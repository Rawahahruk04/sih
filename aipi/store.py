"""The store: what the API reads from, behind one protocol with two backends.

`IndexStore` is the contract. Two things implement it:

  * `SnapshotStore` — runs the pipeline once into memory and serves from it. No
    database, no migrations, no external process: clone, install, `uvicorn`. This is
    what the demo uses, and it is a real code path, not a mock.
  * `SqlStore` (in `aipi.sqlstore`) — reads published vintages from PostgreSQL.

Because the API depends on the protocol and not on either backend, the demo and the
production deployment run identical request-handling code. The only thing that
changes is where the numbers come from, which is exactly the seam you want to be
able to move.

Every series the store returns carries `n_obs` and `coverage_pct` per point. A point
without them is not something this system is willing to publish.
"""

from __future__ import annotations

import calendar
import logging
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol, runtime_checkable

import pandas as pd

from aipi.basket import REFERENCE_WINDOW, SAMPLE_ROUTES
from aipi.cleaning import clean
from aipi.cleaning.pipeline import CleaningReport
from aipi.config import Settings, get_settings
from aipi.index.engine import IndexResult, compute_index
from aipi.index.frequency import month_start as _month_start
from aipi.index.frequency import week_start as _week_start
from aipi.provenance import PipelineRun, build_pipeline_run, methodology_fingerprint
from aipi.validation.backtest import construct_validity_checks
from aipi.validation.cpi_reference import (
    CpiReference,
    CpiReferenceError,
    load_cpi_reference,
)
from aipi.validation.measurement_error import (
    required_sampling_days,
    sampling_error_curve,
    simulate_monthly_sampling,
)

log = logging.getLogger(__name__)

_ROUTE_DISPLAY = {r.route_code: r.display_name for r in SAMPLE_ROUTES}


class SeriesNotFound(KeyError):
    """Requested a series (e.g. an unknown route) the store does not hold."""


def _days_in_month(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


@runtime_checkable
class IndexStore(Protocol):
    """Read model for the API. Implemented by SnapshotStore and SqlStore."""

    def available(self) -> bool: ...
    def latest_index_date(self) -> date | None: ...
    def methodology(self) -> dict: ...
    def pipeline_run(self) -> dict: ...
    def headline(
        self, *, dow_adjusted: bool = False, freq: str = "daily"
    ) -> list[dict]: ...
    def list_routes(self) -> list[dict]: ...
    def route(self, route_code: str) -> list[dict]: ...
    def route_metadata(self) -> list[dict]: ...
    def route_heatmap(
        self, *, start: date | None = None, end: date | None = None
    ) -> dict: ...
    def leadtime_index(self) -> dict[int, list[dict]]: ...
    def leadtime_price_curve(self, *, as_of: date | None = None) -> dict: ...
    def volatility(self) -> dict: ...
    def validation(self) -> dict: ...
    def data_mode_summary(self) -> dict: ...


# ---------------------------------------------------------------------------
# Snapshot: one fully-computed index run, plus the accounting behind it
# ---------------------------------------------------------------------------


@dataclass
class Snapshot:
    result: IndexResult
    report: CleaningReport
    run: PipelineRun
    settings: Settings
    generated_at: datetime
    # per-(date) and per-(cell) observation counts, for honest n_obs on every series
    route_n_obs: dict[tuple[str, date], int]
    leadtime_n_obs: dict[tuple[int, date], int]
    intraday: dict
    #: Pre-computed validation report, when a reference series was supplied.
    #: None means "no reference loaded", which the API reports as such rather
    #: than as a failed validation.
    validation: dict | None = None


def _obs_counts(index_input: pd.DataFrame) -> tuple[dict, dict]:
    """Real n_obs for the route and lead-time series, from the index-eligible rows."""
    route_n: dict[tuple[str, date], int] = defaultdict(int)
    lead_n: dict[tuple[int, date], int] = defaultdict(int)
    for row in index_input.itertuples(index=False):
        d = row.capture_date
        if isinstance(d, pd.Timestamp):
            d = d.date()
        route_n[(str(row.route_code), d)] += 1
        lead_n[(int(row.advance_days), d)] += 1
    return dict(route_n), dict(lead_n)


def _intraday_volatility(raw: pd.DataFrame) -> dict:
    """Within-day fare dispersion across capture slots — the fifth dashboard view.

    Computable only when the collector took more than one slot per offer-day (the
    auxiliary slots the index itself excludes). When it did not, this says so rather
    than manufacturing a number: an empty intraday view is honest, a fabricated one
    is not.

    Measured per offer-day as the coefficient of variation across that day's slots,
    then summarised overall and by advance window. The by-window cut is the point:
    last-minute fares should be visibly more volatile intraday than advance fares,
    which is itself the argument for a disciplined single daily capture slot.
    """
    empty = {
        "available": False,
        "note": "single capture slot per day; no intraday spread to measure",
    }
    if raw.empty:
        return empty
    df = raw.copy()
    for col in ("origin", "destination", "carrier", "flight_no", "advance_days"):
        if col not in df.columns:
            return empty
    df["total_fare"] = pd.to_numeric(df.get("total_fare"), errors="coerce")
    df["advance_days"] = pd.to_numeric(df["advance_days"], errors="coerce")
    df = df.dropna(subset=["total_fare", "advance_days"])
    df = df[df["total_fare"] > 0]
    if df.empty:
        return empty

    cap_date = pd.to_datetime(df["capture_ts"], utc=True, errors="coerce").dt.date
    df = df.assign(_cap_date=cap_date)
    offer = ["_cap_date", "origin", "destination", "advance_days", "carrier", "flight_no"]

    grp = df.groupby(offer)["total_fare"]
    stats = grp.agg(["count", "mean", "std"])
    multi = stats[stats["count"] >= 2].copy()
    if multi.empty:
        return empty
    multi["cv_pct"] = 100.0 * multi["std"] / multi["mean"]

    by_window: dict[str, float] = {}
    adv_level = multi.index.get_level_values("advance_days")
    for adv in sorted(set(adv_level)):
        sel = multi[adv_level == adv]["cv_pct"].dropna()
        if len(sel):
            by_window[str(int(adv))] = round(float(sel.mean()), 3)

    cv = multi["cv_pct"].dropna()
    return {
        "available": True,
        "offer_days_with_multiple_slots": int(len(multi)),
        "mean_intraday_cv_pct": round(float(cv.mean()), 3) if len(cv) else None,
        "p95_intraday_cv_pct": round(float(cv.quantile(0.95)), 3) if len(cv) else None,
        "by_advance_window": by_window,
        "note": (
            "Coefficient of variation of fares within a single day, across capture "
            "slots. These auxiliary slots are excluded from the index; they exist to "
            "quantify the collection noise a drifting capture time would inject."
        ),
    }


def build_snapshot(
    raw: pd.DataFrame,
    *,
    route_weights: Mapping[str, float],
    booking_weights: Mapping[int, float] | None = None,
    settings: Settings | None = None,
    generated_at: datetime | None = None,
    reference: pd.DataFrame | None = None,
    enforce_slot: bool = True,
) -> Snapshot:
    """Collect-clean-index-provenance, once, into an in-memory snapshot.

    `reference` is the DGCA (or synthetic stand-in) monthly average-fare table.
    When supplied, the validation report is computed here and served from the
    snapshot; when omitted, `/validation/dgca` says no reference is loaded rather
    than reporting a failed comparison. The two are different states and the API
    must not conflate them.

    `enforce_slot=False` exists for exactly one caller:
    `aipi.api.deps` loading a live-demo blend (see
    `scripts/run_live_demo.py`). Production data is always captured at the fixed
    daily slot, so this never matters there; a live-demo run happens whenever the
    stage slot in the agenda is, so without this the demo's own live rows would
    be silently re-excluded on every reload — the capture-slot filter doing
    exactly its job, on data it was never designed to see. Never pass `False`
    from any other call site.
    """
    settings = settings or get_settings()
    cleaned = clean(
        raw,
        enforce_slot=enforce_slot,
        min_n_for_trim=settings.min_n_for_trim,
        mad_k=settings.mad_trim_k,
    )
    result = compute_index(
        cleaned.index_input,
        route_weights=route_weights,
        booking_weights=booking_weights,
        settings=settings,
    )
    run = build_pipeline_run(
        input_row_count=cleaned.report.rows_in,
        index_eligible_rows=cleaned.report.rows_index_eligible,
        settings=settings,
        created_at=generated_at,
    )
    route_n, lead_n = _obs_counts(cleaned.index_input)

    validation: dict | None = None
    if reference is not None and not reference.empty:
        from aipi.validation.report import build_validation_report

        # The MoSPI CPI Transport series is real published data and ships with the
        # repo, so it is loaded unconditionally. A failure to load must not take
        # down the primary validation — it is a secondary comparison.
        cpi: CpiReference | None = None
        try:
            cpi = load_cpi_reference()
        except CpiReferenceError as exc:
            log.warning("CPI reference unavailable, secondary comparison skipped: %s", exc)

        validation = build_validation_report(
            daily_index=result.headline,
            route_index=result.route_index,
            reference=reference,
            route_weights=route_weights,
            contributing_rows=cleaned.index_input,
            leadtime_price_curve=result.leadtime_price_curve,
            cpi_reference=cpi,
        ).to_dict()

    return Snapshot(
        result=result,
        report=cleaned.report,
        run=run,
        settings=settings,
        generated_at=generated_at or datetime.now(UTC),
        route_n_obs=route_n,
        leadtime_n_obs=lead_n,
        intraday=_intraday_volatility(raw),
        validation=validation,
    )


# ---------------------------------------------------------------------------
# SnapshotStore
# ---------------------------------------------------------------------------


class SnapshotStore:
    """Serve the API from one in-memory `Snapshot`. The demo backend."""

    def __init__(self, snapshot: Snapshot) -> None:
        self._s = snapshot

    # --- lifecycle ---------------------------------------------------------
    def available(self) -> bool:
        return bool(self._s.result.headline)

    def latest_index_date(self) -> date | None:
        dates = self._s.result.dates
        return dates[-1] if dates else None

    # --- methodology & provenance -----------------------------------------
    def methodology(self) -> dict:
        r = self._s.result
        return {
            "title": "Real-Time Airfare Price Index for India (AIPI)",
            "disclaimer": (
                "Methodology proof of concept for SIH 2026 PS 26056 (MoSPI). "
                "Not an official government statistic."
            ),
            "index_number": {
                "elementary_aggregate": (
                    "Jevons (geometric mean of price RELATIVES) on matched items"
                ),
                "multilateral": (
                    "GEKS-Jevons on a rolling window with movement splice (no revision)"
                ),
                "upper_aggregation": "Laspeyres over base-period EXPENDITURE shares",
                "base_period": "geometric mean of the base window (=100), not a single day",
                "seasonal": "multiplicative day-of-week adjustment",
            },
            "fingerprint": methodology_fingerprint(self._s.settings),
            "base_period": {
                "start": r.base_periods[0].isoformat() if r.base_periods else None,
                "end": r.base_periods[-1].isoformat() if r.base_periods else None,
                "n_days": len(r.base_periods),
            },
            "diagnostics": {
                "dow_amplitude_pct": round(r.dow_amplitude_pct, 4),
                "chain_drift": r.chain_drift,
                "composition_bias_pct": round(r.composition_bias_pct, 4),
            },
            "route_weights": {k: round(v, 6) for k, v in r.route_weights.items()},
            "cleaning": self._s.report.to_dict(),
            "notes": r.notes,
        }

    def pipeline_run(self) -> dict:
        return self._s.run.to_dict()

    # --- series ------------------------------------------------------------
    def _headline_point(self, d: date, value: float) -> dict:
        r = self._s.result
        n = int(r.n_obs.get(d, 0))
        return {
            "date": d.isoformat(),
            "value": round(float(value), 4),
            "n_obs": n,
            "matched_n": int(r.matched_n.get(d, 0)),
            "coverage_pct": round(100.0 * float(r.coverage.get(d, 0.0)), 2),
        }

    def headline(self, *, dow_adjusted: bool = False, freq: str = "daily") -> list[dict]:
        r = self._s.result
        if freq == "daily":
            series = r.headline_dow_adjusted if dow_adjusted else r.headline
            return [self._headline_point(d, series[d]) for d in sorted(series)]

        resampled = r.weekly if freq == "weekly" else r.monthly
        if resampled is None or not resampled.series:
            return []
        # A resampled point's n_obs is the sum over its constituent days, and its
        # coverage is their mean — a weekly point built from three days is not the
        # same statistic as one built from seven, and the consumer must be able to
        # see which they were handed.
        bucket = _week_start if freq == "weekly" else _month_start
        by_period: dict[date, list[date]] = defaultdict(list)
        for d in r.headline:
            by_period[bucket(d)].append(d)

        out: list[dict] = []
        for period in sorted(resampled.series):
            days = by_period.get(period, [])
            n_obs = sum(int(r.n_obs.get(d, 0)) for d in days)
            matched = sum(int(r.matched_n.get(d, 0)) for d in days)
            cov = (
                100.0 * sum(float(r.coverage.get(d, 0.0)) for d in days) / len(days)
                if days
                else 0.0
            )
            # A month observed for 14 days is not a monthly average, and plotted
            # unlabelled beside a 31-day month it invites a comparison that is not
            # valid. The flag is published so the dashboard can dash the line or
            # annotate the point rather than the reader having to infer it.
            expected = 7 if freq == "weekly" else _days_in_month(period)
            out.append(
                {
                    "date": period.isoformat(),
                    "value": round(float(resampled.series[period]), 4),
                    "n_obs": n_obs,
                    "matched_n": matched,
                    "coverage_pct": round(cov, 2),
                    "n_days": len(days),
                    "expected_days": expected,
                    "is_complete": len(days) >= expected,
                }
            )
        return out

    def route_metadata(self) -> list[dict]:
        """Route dimension for frontend dropdowns — no series, just identity."""
        r = self._s.result
        out = []
        for route in SAMPLE_ROUTES:
            out.append(
                {
                    "route_code": route.route_code,
                    "origin": route.origin,
                    "destination": route.destination,
                    "display_name": route.display_name,
                    "weight": round(float(r.route_weights.get(route.route_code, 0.0)), 6),
                    "in_index": route.route_code in r.route_index,
                }
            )
        return out

    def route_heatmap(
        self, *, start: date | None = None, end: date | None = None
    ) -> dict:
        """Route x date matrix, shaped for direct heatmap rendering.

        Returned as parallel `routes` / `dates` / `matrix` arrays rather than a
        list of records because a heatmap component wants a grid, and reshaping
        thousands of records in the browser is work the API can do once. Missing
        cells are `null`, never 0 — a route with no index on a date has no value,
        and rendering that as zero would paint a fare collapse that did not
        happen.
        """
        r = self._s.result
        all_dates = sorted(r.headline)
        if start:
            all_dates = [d for d in all_dates if d >= start]
        if end:
            all_dates = [d for d in all_dates if d <= end]

        routes = sorted(
            r.route_index, key=lambda rc: -float(r.route_weights.get(rc, 0.0))
        )
        matrix: list[list[float | None]] = []
        for rc in routes:
            series = r.route_index.get(rc, {})
            matrix.append(
                [
                    round(float(series[d]), 4) if d in series else None
                    for d in all_dates
                ]
            )

        present = [v for row in matrix for v in row if v is not None]
        return {
            "routes": routes,
            "route_names": [_ROUTE_DISPLAY.get(rc, rc) for rc in routes],
            "dates": [d.isoformat() for d in all_dates],
            "matrix": matrix,
            "value_min": round(min(present), 4) if present else None,
            "value_max": round(max(present), 4) if present else None,
            "baseline": 100.0,
            "note": (
                "matrix[i][j] is route routes[i] on dates[j]. null means the route "
                "produced no index that day; it is not zero."
            ),
        }

    def data_mode_summary(self) -> dict:
        """Real-vs-synthetic lineage of the rows behind the current index."""
        counts = dict(self._s.report.data_mode_breakdown)
        total = sum(counts.values())
        real = counts.get("real", 0)
        synthetic = counts.get("synthetic", 0)
        return {
            "counts": counts,
            "total_rows": total,
            "real_share": round(real / total, 6) if total else 0.0,
            "synthetic_share": round(synthetic / total, 6) if total else 0.0,
            "is_demo_data": synthetic > 0,
            "banner": (
                None
                if total and synthetic == 0
                else "Contains simulated data — not a measurement of real airfares."
            ),
        }

    def validation(self) -> dict:
        """DGCA back-test report. Empty-but-explained when no reference is loaded."""
        if self._s.validation is None:
            return {
                "available": False,
                "reason": (
                    "No reference series is loaded in this store. Run "
                    "scripts/seed_synthetic.py for a synthetic reference, or load "
                    "DGCA monthly average fares, then rebuild the snapshot."
                ),
                "data_mode_breakdown": self.data_mode_summary(),
            }
        return self._s.validation

    def list_routes(self) -> list[dict]:
        r = self._s.result
        out = []
        for code, series in r.route_index.items():
            if not series:
                continue
            last = max(series)
            out.append(
                {
                    "route_code": code,
                    "display_name": _ROUTE_DISPLAY.get(code, code),
                    "weight": round(float(r.route_weights.get(code, 0.0)), 6),
                    "latest_date": last.isoformat(),
                    "latest_value": round(float(series[last]), 4),
                }
            )
        return sorted(out, key=lambda x: -x["weight"])

    def route(self, route_code: str) -> list[dict]:
        r = self._s.result
        series = r.route_index.get(route_code)
        if not series:
            raise SeriesNotFound(route_code)
        n_windows = len({adv for (rc, adv) in r.cell_index if rc == route_code}) or 1
        present = defaultdict(int)
        for (rc, _adv), cser in r.cell_index.items():
            if rc == route_code:
                for d in cser:
                    present[d] += 1
        out = []
        for d in sorted(series):
            out.append(
                {
                    "date": d.isoformat(),
                    "value": round(float(series[d]), 4),
                    "n_obs": int(self._s.route_n_obs.get((route_code, d), 0)),
                    "coverage_pct": round(100.0 * present.get(d, 0) / n_windows, 2),
                }
            )
        return out

    def leadtime_index(self) -> dict[int, list[dict]]:
        r = self._s.result
        n_routes = len(r.route_weights) or 1
        out: dict[int, list[dict]] = {}
        for window, series in sorted(r.leadtime_index.items()):
            present = defaultdict(int)
            for (_rc, adv), cser in r.cell_index.items():
                if adv == window:
                    for d in cser:
                        present[d] += 1
            pts = []
            for d in sorted(series):
                pts.append(
                    {
                        "date": d.isoformat(),
                        "value": round(float(series[d]), 4),
                        "n_obs": int(self._s.leadtime_n_obs.get((window, d), 0)),
                        "coverage_pct": round(100.0 * present.get(d, 0) / n_routes, 2),
                    }
                )
            out[window] = pts
        return out

    def leadtime_price_curve(self, *, as_of: date | None = None) -> dict:
        r = self._s.result
        curve_by_date = r.leadtime_price_curve
        if not curve_by_date:
            return {"as_of": None, "reference_window": None, "curve": []}
        chosen = as_of if (as_of in curve_by_date) else max(curve_by_date)
        curve = curve_by_date[chosen]
        return {
            "as_of": chosen.isoformat(),
            "reference_window": REFERENCE_WINDOW,
            "note": (
                f"Relative fare LEVEL by advance window, {REFERENCE_WINDOW}-day "
                "window = 100. Pooled over the trailing 7 captures so each window "
                "spans a full week of travel weekdays — without that, window and "
                "weekday are confounded and the curve can invert."
            ),
            "curve": [
                {"advance_days": int(w), "relative_level": round(float(curve[w]), 3)}
                for w in sorted(curve)
            ],
        }

    def volatility(self) -> dict:
        r = self._s.result
        checks = construct_validity_checks(
            r.headline, leadtime_price_curve=r.leadtime_price_curve
        )
        payload: dict = {
            "daily": {
                "daily_volatility_pct": checks.get("daily_volatility_pct"),
                "max_daily_move_pct": checks.get("max_daily_move_pct"),
                "suspiciously_flat": checks.get("suspiciously_flat"),
            },
            "intraday": self._s.intraday,
        }
        try:
            me = simulate_monthly_sampling(r.headline, days_per_month=1)
            payload["sampling_error"] = {
                "headline": me.headline_sentence(),
                "one_day_per_month": me.to_dict(),
                "curve": sampling_error_curve(r.headline),
                "required_days_for_1pct_mae": required_sampling_days(
                    r.headline, target_mae_pct=1.0
                ),
            }
        except ValueError as exc:
            payload["sampling_error"] = {"available": False, "reason": str(exc)}
        return payload
