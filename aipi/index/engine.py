"""Index engine orchestrator: clean fares in, publishable index out.

Ordering here is load-bearing. In particular every cell index must be rebased to
a COMMON base period *before* upper-level aggregation. Cells enter the sample on
different dates (a route/window pair may have no estimable index until day 4),
so aggregating cell indices that are each self-normalised to their own first
observed day would average numbers expressed on different bases — a silent,
plausible-looking error that no test of the individual formulas would catch.

Input contract (one row per accepted observation):
    capture_date  : datetime.date
    route_code    : str
    advance_days  : int
    item_key      : str      (see basket.item_key)
    total_fare    : float    (> 0, INR, per passenger, incl. taxes)
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from aipi.basket import REFERENCE_WINDOW
from aipi.config import Settings, get_settings
from aipi.index.aggregate import (
    headline_coverage,
    index_spread,
    laspeyres_headline,
    rebase_to_period_mean,
    select_base_periods,
    tornqvist_headline,
    uniform_booking_weights,
    window_aggregate,
)
from aipi.index.dow import adjust_series, dow_amplitude_pct, estimate_dow_factors
from aipi.index.elementary import (
    chained_jevons,
    geometric_mean,
    matched_sample_sizes,
    naive_gm_level_index,
)
from aipi.index.frequency import ResampleResult, to_monthly, to_weekly
from aipi.index.geks import drift_diagnostic, rolling_geks_jevons

REQUIRED_COLUMNS = ("capture_date", "route_code", "advance_days", "item_key", "total_fare")

#: Reference window for the lead-time PRICE curve, tracked from the basket so
#: the mandated window set and the curve anchor can never drift apart.
REF_WINDOW = REFERENCE_WINDOW


@dataclass
class IndexResult:
    """Everything the API and the validation module need, and nothing derived twice."""

    base_periods: list[date]
    headline: dict[date, float]
    headline_dow_adjusted: dict[date, float]
    route_index: dict[str, dict[date, float]]
    leadtime_index: dict[int, dict[date, float]]
    cell_index: dict[tuple[str, int], dict[date, float]]

    #: Superlative cross-check on the same route indices. Published beside the
    #: headline, never instead of it — see `aggregate.tornqvist_headline`.
    headline_tornqvist: dict[date, float] = field(default_factory=dict)
    #: Laspeyres-vs-Törnqvist divergence: the substitution-bias estimate.
    formula_spread: dict[str, float] = field(default_factory=dict)

    #: PS 26056 requires daily, weekly and monthly. Weekly/monthly are derived
    #: from `headline` by chaining, never by averaging index levels.
    weekly: ResampleResult | None = None
    monthly: ResampleResult | None = None

    #: Relative fare LEVEL by advance window, reference window = 100. Distinct
    #: from `leadtime_index`, and the two answer different questions:
    #:   leadtime_index       — how fast each window's fares are inflating
    #:   leadtime_price_curve — how much more a late booking costs than an early one
    #: Only the price curve should be monotone in advance days; expecting that of
    #: `leadtime_index` is a category error, since every window's index is 100 at
    #: the base period by construction.
    leadtime_price_curve: dict[date, dict[int, float]] = field(default_factory=dict)

    # --- statistical accompaniment. A number without these is not a statistic.
    n_obs: dict[date, int] = field(default_factory=dict)
    matched_n: dict[date, int] = field(default_factory=dict)
    coverage: dict[date, float] = field(default_factory=dict)

    # --- specification diagnostics, published as evidence
    dow_factors: dict[int, float] = field(default_factory=dict)
    dow_amplitude_pct: float = 0.0
    chain_drift: dict[str, float] = field(default_factory=dict)
    composition_bias_pct: float = 0.0
    route_weights: dict[str, float] = field(default_factory=dict)
    booking_weights: dict[int, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def dates(self) -> list[date]:
        return sorted(self.headline)


def build_panels(df: pd.DataFrame) -> dict[tuple[str, int], dict[date, dict[str, float]]]:
    """Group accepted observations into per-cell matched-model panels."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"clean fares missing required columns: {missing}")

    panels: dict[tuple[str, int], dict[date, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for row in df.itertuples(index=False):
        fare = float(row.total_fare)
        if fare <= 0:
            raise ValueError(f"non-positive fare reached the index engine: {row!r}")
        cell = (str(row.route_code), int(row.advance_days))
        cdate = row.capture_date
        if isinstance(cdate, pd.Timestamp):
            cdate = cdate.date()
        panels[cell][cdate][str(row.item_key)] = fare

    return {cell: dict(periods) for cell, periods in panels.items()}


def compute_index(
    df: pd.DataFrame,
    *,
    route_weights: Mapping[str, float],
    booking_weights: Mapping[int, float] | None = None,
    settings: Settings | None = None,
) -> IndexResult:
    """Run the full three-level index.

    Args:
        route_weights: base-period EXPENDITURE shares per route. Build these with
            `aggregate.expenditure_weights`, not from passenger counts alone.
        booking_weights: advance-window booking shares. Uniform fallback is
            applied and recorded in ``notes`` when omitted.
    """
    settings = settings or get_settings()
    notes: list[str] = []

    panels = build_panels(df)
    if not panels:
        raise ValueError("no observations supplied to the index engine")

    if booking_weights is None:
        windows = sorted({adv for _, adv in panels})
        booking_weights = uniform_booking_weights(windows)
        notes.append(
            "Booking-share weights unavailable; uniform weights across advance windows "
            "applied as a documented fallback."
        )

    # --- L1: elementary index per cell (drift-free), plus comparison series -----
    cell_geks: dict[tuple[str, int], dict[date, float]] = {}
    cell_chained: dict[tuple[str, int], dict[date, float]] = {}
    cell_naive: dict[tuple[str, int], dict[date, float]] = {}
    for cell, panel in panels.items():
        if len(panel) < 2:
            notes.append(f"Cell {cell} has a single capture date; excluded from the index.")
            continue
        cell_geks[cell] = rolling_geks_jevons(
            panel, window=settings.geks_window_days, min_matched=settings.min_matched_items
        )
        cell_chained[cell] = chained_jevons(panel, min_matched=settings.min_matched_items)
        cell_naive[cell] = naive_gm_level_index(panel)

    if not cell_geks:
        raise ValueError("no cell produced an estimable elementary index")

    # --- common base period, chosen from cell-level availability ----------------
    cell_coverage = _cell_coverage(cell_geks)
    base_periods = select_base_periods(cell_coverage, n_days=settings.base_period_days)
    if len(base_periods) < settings.base_period_days:
        notes.append(
            f"Base period shortened to {len(base_periods)} day(s); series is short. "
            "Base = geometric mean over these dates."
        )

    # Rebase EVERY cell onto the shared base period before aggregating.
    cell_geks = _rebase_cells(cell_geks, base_periods, notes)
    cell_chained = _rebase_cells(cell_chained, base_periods, notes=None)

    # --- L2: cells -> routes ----------------------------------------------------
    route_index = window_aggregate(cell_geks, booking_weights)
    route_chained = window_aggregate(cell_chained, booking_weights)

    # --- L3: routes -> headline (Laspeyres, expenditure weights) ----------------
    headline = laspeyres_headline(route_index, route_weights)
    headline_chained = laspeyres_headline(route_chained, route_weights)
    coverage = headline_coverage(route_index, route_weights)

    # Superlative cross-check on identical inputs. No current-period expenditure
    # data is observed, so this reduces to Laspeyres by construction; the note
    # says so rather than letting an unexplained zero gap read as a validation.
    headline_tq = tornqvist_headline(route_index, route_weights)
    spread = index_spread(headline, headline_tq)
    notes.append(
        "Törnqvist cross-check computed on base-period weights only (no observed "
        "current-period route expenditure), so it coincides with Laspeyres by "
        "construction. Substitution bias is therefore NOT yet estimated — this "
        "becomes informative once route-level passenger data is refreshed per period."
    )

    # --- lead-time curve: cells -> window, weighted across routes ---------------
    leadtime_index = _leadtime_curve(cell_geks, route_weights)
    leadtime_price_curve = compute_leadtime_price_curve(panels, route_weights)

    # --- day-of-week adjustment -------------------------------------------------
    dow_factors = estimate_dow_factors(headline)
    headline_adj = adjust_series(headline, dow_factors)
    amplitude = dow_amplitude_pct(dow_factors)
    if dow_factors == dict.fromkeys(range(7), 1.0):
        notes.append(
            "Series too short to identify day-of-week factors; adjusted series equals raw."
        )

    # --- diagnostics ------------------------------------------------------------
    drift = drift_diagnostic(headline_chained, headline)
    composition_bias = _composition_bias_pct(cell_geks, cell_naive, base_periods)

    # --- frequency resampling (PS-mandated daily / weekly / monthly) ------------
    weekly = to_weekly(headline)
    monthly = to_monthly(headline)

    return IndexResult(
        base_periods=list(base_periods),
        headline=headline,
        headline_dow_adjusted=headline_adj,
        headline_tornqvist=headline_tq,
        formula_spread=spread,
        weekly=weekly,
        monthly=monthly,
        route_index={r: dict(s) for r, s in route_index.items()},
        leadtime_index=leadtime_index,
        leadtime_price_curve=leadtime_price_curve,
        cell_index=cell_geks,
        n_obs=_daily_obs_counts(df),
        matched_n=_daily_matched_counts(panels),
        coverage=coverage,
        dow_factors=dow_factors,
        dow_amplitude_pct=amplitude,
        chain_drift=drift,
        composition_bias_pct=composition_bias,
        route_weights=dict(route_weights),
        booking_weights=dict(booking_weights),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _cell_coverage(
    cell_series: Mapping[tuple[str, int], Mapping[date, float]],
) -> dict[date, float]:
    """Fraction of cells producing an index on each date."""
    total = len(cell_series)
    counts: dict[date, int] = defaultdict(int)
    for series in cell_series.values():
        for d in series:
            counts[d] += 1
    return {d: c / total for d, c in counts.items()} if total else {}


def _rebase_cells(
    cell_series: Mapping[tuple[str, int], Mapping[date, float]],
    base_periods: Sequence[date],
    notes: list[str] | None,
) -> dict[tuple[str, int], dict[date, float]]:
    out: dict[tuple[str, int], dict[date, float]] = {}
    for cell, series in cell_series.items():
        try:
            out[cell] = rebase_to_period_mean(series, base_periods)
        except ValueError:
            # No observation in the base window: the cell cannot be expressed on
            # the common base, so it is excluded rather than approximated.
            if notes is not None:
                notes.append(f"Cell {cell} absent from base period; excluded from aggregation.")
    return out


def _leadtime_curve(
    cell_series: Mapping[tuple[str, int], Mapping[date, float]],
    route_weights: Mapping[str, float],
) -> dict[int, dict[date, float]]:
    by_window: dict[int, dict[str, dict[date, float]]] = defaultdict(dict)
    for (route_code, advance_days), series in cell_series.items():
        by_window[int(advance_days)][route_code] = dict(series)
    return {
        window: laspeyres_headline(routes, route_weights)
        for window, routes in sorted(by_window.items())
    }


#: Trailing capture dates pooled into each published lead-time curve point.
#:
#: This is not cosmetic smoothing. On a single capture date, advance window and
#: travel weekday are CONFOUNDED by construction: travel_date = capture_date +
#: window, so two windows an odd number of days apart always sample different
#: weekdays. Under the PS-mandated set (1, 7, 15, 30, 45) every consecutive pair
#: differs by 1 modulo 7, so the weekday effect — worth up to ~15% between a
#: Tuesday and a Friday departure — sits directly on top of a lead-time gap of
#: ~6%, and can invert it.
#:
#: Pooling over exactly 7 consecutive capture dates makes each window span all
#: seven travel weekdays once, so the weekday effect cancels EXACTLY rather than
#: being modelled away. Any smaller window leaves the confound in place.
CURVE_POOL_DAYS = 7


def compute_leadtime_price_curve(
    panels: Mapping[tuple[str, int], Mapping[date, Mapping[str, float]]],
    route_weights: Mapping[str, float],
    *,
    ref_window: int = REF_WINDOW,
    pool_days: int = CURVE_POOL_DAYS,
) -> dict[date, dict[int, float]]:
    """Relative fare LEVEL by advance window, reference window = 100.

    Computed per route first and only then pooled, because routes differ by a
    factor of two in absolute fare. Pooling raw levels would make the curve a
    statement about which routes happened to report today rather than about
    lead-time pricing.

    Pooling across routes is geometric and weighted, consistent with the
    elementary aggregate: a ratio averaged arithmetically is not a ratio.

    Each published point additionally pools the trailing `pool_days` capture
    dates to break the window/weekday confound — see `CURVE_POOL_DAYS`.
    """
    # route -> window -> date -> geometric-mean fare
    gm: dict[str, dict[int, dict[date, float]]] = defaultdict(lambda: defaultdict(dict))
    for (route_code, advance_days), periods in panels.items():
        for period, prices in periods.items():
            vals = [v for v in prices.values() if v > 0]
            if vals:
                gm[route_code][int(advance_days)][period] = geometric_mean(vals)

    all_dates: set[date] = set()
    all_windows: set[int] = set()
    for windows in gm.values():
        for w, series in windows.items():
            all_windows.add(w)
            all_dates |= set(series)

    # Per-date log relatives against the reference window, before pooling.
    per_date: dict[date, dict[int, tuple[float, float]]] = {}
    for period in sorted(all_dates):
        day: dict[int, tuple[float, float]] = {}
        for window in sorted(all_windows):
            log_sum = 0.0
            wsum = 0.0
            for route_code, windows in gm.items():
                ref = windows.get(ref_window, {}).get(period)
                val = windows.get(window, {}).get(period)
                w = float(route_weights.get(route_code, 0.0))
                if not ref or not val or w <= 0:
                    continue
                log_sum += w * math.log(val / ref)
                wsum += w
            if wsum > 0:
                day[window] = (log_sum / wsum, wsum)
        if day:
            per_date[period] = day

    # Pool the trailing `pool_days` captures so every window covers a full week
    # of travel weekdays. Averaging happens in LOG space — these are ratios.
    ordered = sorted(per_date)
    out: dict[date, dict[int, float]] = {}
    for i, period in enumerate(ordered):
        window_start = max(0, i - pool_days + 1)
        pooled_dates = ordered[window_start : i + 1]
        curve: dict[int, float] = {}
        for window in sorted(all_windows):
            logs = [
                per_date[d][window][0] for d in pooled_dates if window in per_date[d]
            ]
            if logs:
                curve[window] = 100.0 * math.exp(sum(logs) / len(logs))
        if curve:
            out[period] = curve
    return out


def _daily_obs_counts(df: pd.DataFrame) -> dict[date, int]:
    counts: dict[date, int] = defaultdict(int)
    for cdate in df["capture_date"]:
        d = cdate.date() if isinstance(cdate, pd.Timestamp) else cdate
        counts[d] += 1
    return dict(counts)


def _daily_matched_counts(
    panels: Mapping[tuple[str, int], Mapping[date, Mapping[str, float]]],
) -> dict[date, int]:
    totals: dict[date, int] = defaultdict(int)
    for panel in panels.values():
        for d, n in matched_sample_sizes(panel).items():
            totals[d] += n
    return dict(totals)


def _composition_bias_pct(
    correct: Mapping[tuple[str, int], Mapping[date, float]],
    naive: Mapping[tuple[str, int], Mapping[date, float]],
    base_periods: Sequence[date],
) -> float:
    """Mean absolute gap between the matched index and the GM-of-levels index.

    Quantifies how much a naive implementation would have mistaken schedule churn
    for inflation. Reported, not hidden.
    """
    gaps: list[float] = []
    for cell, good in correct.items():
        raw = naive.get(cell)
        if not raw:
            continue
        try:
            bad = rebase_to_period_mean(raw, base_periods)
        except ValueError:
            continue
        for d, level in good.items():
            other = bad.get(d)
            if other and level:
                gaps.append(abs(100.0 * (other - level) / level))
    return sum(gaps) / len(gaps) if gaps else 0.0
