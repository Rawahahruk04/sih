"""Levels 2 and 3 — window aggregation and the Laspeyres headline.

The weighting error this module exists to prevent
-------------------------------------------------
A Laspeyres price index aggregates elementary indices with base-period
**expenditure** shares:

    w_r  =  p_r0 * q_r0  /  sum_r p_r0 * q_r0

DGCA publishes city-pair *passenger volumes*, which are q_r0 — quantity shares,
not expenditure shares. Weighting by passenger share alone systematically
under-weights expensive long routes (DEL-GAU) against cheap dense ones
(DEL-BOM), because it prices every passenger as if they spent the same amount.

`expenditure_weights` builds the correct weight from passengers x base-period
average fare. `quantity_weights` is retained so both can be reported and the
divergence quantified — a specification test, not a hedge.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date

#: (route_code, advance_days) -> {period -> index level}
CellSeries = Mapping[tuple[str, int], Mapping[date, float]]
#: route_code -> {period -> index level}
RouteSeries = Mapping[str, Mapping[date, float]]


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------


def _normalise(raw: Mapping[str, float]) -> dict[str, float]:
    total = sum(raw.values())
    if total <= 0:
        raise ValueError("weights sum to zero")
    return {k: v / total for k, v in raw.items()}


def expenditure_weights(
    passengers: Mapping[str, float],
    base_avg_fare: Mapping[str, float],
) -> dict[str, float]:
    """Base-period expenditure shares — the correct Laspeyres weights.

    Args:
        passengers: base-period passengers carried per route (DGCA traffic).
        base_avg_fare: base-period average fare per route (DGCA fare data or,
            documented as such, the collected base-period mean).
    """
    routes = sorted(set(passengers) & set(base_avg_fare))
    if not routes:
        raise ValueError("no routes common to passengers and base_avg_fare")
    raw = {r: float(passengers[r]) * float(base_avg_fare[r]) for r in routes}
    return _normalise(raw)


def quantity_weights(passengers: Mapping[str, float]) -> dict[str, float]:
    """Passenger-volume shares. NOT Laspeyres weights — comparison series only."""
    return _normalise({k: float(v) for k, v in passengers.items()})


def weight_divergence(
    exp_w: Mapping[str, float], qty_w: Mapping[str, float]
) -> dict[str, float]:
    """Per-route difference in weight, in basis points. Reported alongside both."""
    routes = sorted(set(exp_w) | set(qty_w))
    return {r: 10_000.0 * (exp_w.get(r, 0.0) - qty_w.get(r, 0.0)) for r in routes}


#: Share of bookings made in each advance-purchase window. Uniform is the
#: DOCUMENTED FALLBACK, used only until real Indian booking-curve data is
#: substituted. It is a stated assumption, never a silent default.
UNIFORM_BOOKING_WEIGHTS: dict[int, float] = {}


def uniform_booking_weights(windows: Sequence[int]) -> dict[int, float]:
    return {int(w): 1.0 / len(windows) for w in windows}


# ---------------------------------------------------------------------------
# Level 2 — cells to route
# ---------------------------------------------------------------------------


def window_aggregate(
    cell_series: CellSeries,
    booking_weights: Mapping[int, float],
) -> dict[str, dict[date, float]]:
    """Aggregate (route x window) elementary indices to a route index.

    Weighted arithmetic mean of index levels, mirroring CPI's upper-level
    aggregation. Weights are renormalised over the windows actually present on
    each date, so a missing window reduces coverage rather than silently
    dragging the route index toward zero.
    """
    by_route: dict[str, dict[date, list[tuple[float, float]]]] = {}
    for (route_code, advance_days), series in cell_series.items():
        w = float(booking_weights.get(int(advance_days), 0.0))
        if w <= 0:
            continue
        for period, level in series.items():
            by_route.setdefault(route_code, {}).setdefault(period, []).append((w, float(level)))

    out: dict[str, dict[date, float]] = {}
    for route_code, per_period in by_route.items():
        out[route_code] = {}
        for period, pairs in per_period.items():
            wsum = sum(w for w, _ in pairs)
            if wsum <= 0:
                continue
            out[route_code][period] = sum(w * lv for w, lv in pairs) / wsum
    return out


# ---------------------------------------------------------------------------
# Level 3 — routes to headline
# ---------------------------------------------------------------------------


def laspeyres_headline(
    route_series: RouteSeries,
    route_weights: Mapping[str, float],
) -> dict[date, float]:
    """Weighted (Laspeyres) aggregation of route indices to the headline.

    Weights are renormalised over routes present on each date. The resulting
    coverage is reported separately by `headline_coverage` — a headline computed
    from 6 of 10 routes is a different statistic from one computed from all 10,
    and consumers must be able to see which they were given.
    """
    periods: set[date] = set()
    for series in route_series.values():
        periods |= set(series)

    out: dict[date, float] = {}
    for period in sorted(periods):
        num = 0.0
        wsum = 0.0
        for route_code, series in route_series.items():
            level = series.get(period)
            w = float(route_weights.get(route_code, 0.0))
            if level is None or w <= 0:
                continue
            num += w * float(level)
            wsum += w
        if wsum > 0:
            out[period] = num / wsum
    return out


def headline_coverage(
    route_series: RouteSeries,
    route_weights: Mapping[str, float],
) -> dict[date, float]:
    """Fraction of total route WEIGHT (not route count) present on each date."""
    total_w = sum(float(w) for w in route_weights.values())
    periods: set[date] = set()
    for series in route_series.values():
        periods |= set(series)

    out: dict[date, float] = {}
    for period in sorted(periods):
        present = sum(
            float(route_weights.get(rc, 0.0)) for rc, s in route_series.items() if period in s
        )
        out[period] = present / total_w if total_w > 0 else 0.0
    return out


# ---------------------------------------------------------------------------
# Base period
# ---------------------------------------------------------------------------


def rebase_to_period_mean(
    series: Mapping[date, float],
    base_periods: Sequence[date],
    *,
    base: float = 100.0,
) -> dict[date, float]:
    """Rebase so the GEOMETRIC MEAN of ``base_periods`` equals ``base``.

    Anchoring on a single day lets one noisy day distort every value in the
    series forever. CPI sets base-*year* average = 100; the daily analogue is a
    base-period average, computed geometrically because the index is
    multiplicative.
    """
    anchors = [float(series[p]) for p in base_periods if p in series and series[p] > 0]
    if not anchors:
        raise ValueError("no valid observations in base period")
    anchor = math.exp(sum(math.log(a) for a in anchors) / len(anchors))
    return {p: base * float(v) / anchor for p, v in series.items()}


def select_base_periods(
    coverage: Mapping[date, float],
    *,
    n_days: int,
    min_coverage: float = 0.95,
) -> list[date]:
    """First ``n_days`` consecutive dates meeting ``min_coverage``.

    Deterministic and stated, rather than eyeballed for cleanliness. If no such
    run exists the threshold is relaxed once and the relaxation is surfaced by
    the caller in `/methodology`.
    """
    dates = sorted(coverage)
    for threshold in (min_coverage, 0.0):
        run: list[date] = []
        for d in dates:
            if coverage[d] >= threshold:
                run.append(d)
                if len(run) == n_days:
                    return run
            else:
                run = []
    return dates[:n_days]
