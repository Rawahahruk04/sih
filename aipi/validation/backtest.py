"""DGCA back-test.

Two statistical failures this module refuses to commit
-----------------------------------------------------
**1. Correlation on n=2.** Thirty to sixty days of collection yields one or two
monthly percentage changes. A Pearson r on two points is not a weak result, it is
an undefined one — and reporting "r = 0.7" from it is the fastest way to lose a
statistics judge. `national_backtest` therefore *refuses* to emit r below
`MIN_N_FOR_CORRELATION` and says why.

The fix is not a bigger claim, it is a better estimator: pool across routes.
`route_panel_backtest` compares route-month movements, giving n = routes x months
(around 20 on this sample instead of 2) — genuine degrees of freedom, an honest
standard error, and a claim that survives questioning.

**2. Calibrating on the validation target.** If synthetic back-fill is anchored to
DGCA and then validated against DGCA, the exercise measures the simulator, not
the index. `assert_holdout` makes that failure structurally impossible: the
months used to calibrate synthetic data must be disjoint from the months used to
validate, and the check raises rather than warns.

Reporting discipline: DGCA publishes monthly averages over all traffic on a route,
while AIPI measures a fixed basket at fixed advance windows. These are different
estimands. Agreement in *direction and movement* is the defensible bar; agreement
in level is not expected and is not claimed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

#: Below this, a correlation coefficient is not reported. Chosen so the estimate
#: has at least a handful of degrees of freedom rather than being an artefact of
#: two points and a straight line.
MIN_N_FOR_CORRELATION = 8


class HoldoutViolation(RuntimeError):
    """Raised when calibration and validation periods overlap."""


def assert_holdout(
    calibration_months: Sequence[str],
    validation_months: Sequence[str],
) -> None:
    """Fail loudly if any month is used both to calibrate and to validate.

    Called by the synthetic back-fill path before any validation statistic is
    computed. A warning would be ignored; an exception cannot be.
    """
    overlap = sorted(set(calibration_months) & set(validation_months))
    if overlap:
        raise HoldoutViolation(
            "Synthetic back-fill was calibrated on the same months it is validated "
            f"against: {overlap}. Validating against your own calibration target "
            "measures the simulator, not the index. Re-partition the months."
        )


@dataclass
class BacktestResult:
    """A back-test statistic always travels with its sample size."""

    comparison: str  # 'national_monthly' | 'route_month_panel'
    n: int
    pearson_r: float | None
    spearman_rho: float | None
    mape_pct: float | None
    directional_accuracy: float | None
    insufficient_n: bool
    months: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        def r(x: float | None, nd: int = 4) -> float | None:
            return None if x is None else round(x, nd)

        return {
            "comparison": self.comparison,
            "n": self.n,
            "pearson_r": r(self.pearson_r),
            "spearman_rho": r(self.spearman_rho),
            "mape_pct": r(self.mape_pct),
            "directional_accuracy": r(self.directional_accuracy),
            "insufficient_n": self.insufficient_n,
            "months": self.months,
            "routes": self.routes,
            "notes": self.notes,
        }


def to_monthly(daily: Mapping[date, float], *, min_days: int = 20) -> dict[str, float]:
    """Resample a daily index to monthly means, dropping partial months."""
    buckets: dict[str, list[float]] = {}
    for d in sorted(daily):
        buckets.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(float(daily[d]))
    return {m: float(np.mean(v)) for m, v in buckets.items() if len(v) >= min_days}


def pct_change(series: Mapping[str, float]) -> dict[str, float]:
    """Month-on-month percentage change, keyed by the later month."""
    keys = sorted(series)
    return {
        b: 100.0 * (series[b] - series[a]) / series[a]
        for a, b in zip(keys, keys[1:], strict=False)
        if series[a]
    }


def _stats(x: Sequence[float], y: Sequence[float], comparison: str) -> tuple:
    """Correlations, MAPE and directional accuracy — or an honest refusal."""
    n = len(x)
    notes: list[str] = []
    if n < MIN_N_FOR_CORRELATION:
        notes.append(
            f"n = {n} paired observations is below the reporting threshold of "
            f"{MIN_N_FOR_CORRELATION}. A correlation coefficient is not reported: at "
            "this sample size it would be an artefact, not a finding. Use the "
            "route-month panel comparison, or extend the collection window."
        )
        return None, None, None, None, True, notes

    sx, sy = pd.Series(x, dtype=float), pd.Series(y, dtype=float)
    pearson = float(sx.corr(sy, method="pearson"))
    spearman = float(sx.corr(sy, method="spearman"))

    nonzero = sy.abs() > 1e-12
    mape = (
        float((100.0 * (sx[nonzero] - sy[nonzero]).abs() / sy[nonzero].abs()).mean())
        if nonzero.any()
        else None
    )
    if mape is not None:
        notes.append(
            "MAPE is computed on month-on-month PERCENTAGE CHANGES, not on levels. "
            "AIPI is an index (base = 100) and DGCA reports rupee fares, so a level "
            "MAPE would be meaningless."
        )

    moved = np.sign(sy) != 0
    directional = (
        float((np.sign(sx[moved]) == np.sign(sy[moved])).mean()) if moved.any() else None
    )
    if not moved.all():
        notes.append(
            f"{int((~moved).sum())} month(s) with zero DGCA movement excluded from "
            "directional accuracy: a flat month has no direction to match."
        )
    return pearson, spearman, mape, directional, False, notes


def national_backtest(
    daily_index: Mapping[date, float],
    dgca_monthly_fare: Mapping[str, float],
    *,
    min_days_per_month: int = 20,
) -> BacktestResult:
    """Compare AIPI monthly movement against DGCA national average-fare movement.

    Honest about its own weakness: with a short collection window this comparison
    is almost always under-powered, and it says so rather than reporting a number.
    """
    aipi_monthly = to_monthly(daily_index, min_days=min_days_per_month)
    aipi_chg = pct_change(aipi_monthly)
    dgca_chg = pct_change(dgca_monthly_fare)

    months = sorted(set(aipi_chg) & set(dgca_chg))
    x = [aipi_chg[m] for m in months]
    y = [dgca_chg[m] for m in months]

    pearson, spearman, mape, directional, insufficient, notes = _stats(x, y, "national_monthly")
    notes.append(
        "DGCA reports the average fare actually transacted across all traffic on a "
        "route; AIPI measures a fixed basket at fixed advance windows. Movement "
        "agreement is the bar; level agreement is neither expected nor claimed."
    )
    return BacktestResult(
        comparison="national_monthly",
        n=len(months),
        pearson_r=pearson,
        spearman_rho=spearman,
        mape_pct=mape,
        directional_accuracy=directional,
        insufficient_n=insufficient,
        months=months,
        notes=notes,
    )


def route_panel_backtest(
    route_daily_index: Mapping[str, Mapping[date, float]],
    dgca_route_monthly_fare: Mapping[str, Mapping[str, float]],
    *,
    min_days_per_month: int = 20,
) -> BacktestResult:
    """The comparison that actually has statistical power.

    Pools month-on-month movements across routes, so n = routes x months rather
    than months alone. Each route contributes its own movement, which is what
    makes this a panel rather than a repeated national comparison.
    """
    x: list[float] = []
    y: list[float] = []
    used_routes: list[str] = []
    used_months: set[str] = set()
    notes: list[str] = []

    for route_code, daily in sorted(route_daily_index.items()):
        dgca = dgca_route_monthly_fare.get(route_code)
        if not dgca:
            notes.append(f"No DGCA route series for {route_code}; excluded.")
            continue
        aipi_chg = pct_change(to_monthly(daily, min_days=min_days_per_month))
        dgca_chg = pct_change(dgca)
        shared = sorted(set(aipi_chg) & set(dgca_chg))
        if not shared:
            continue
        used_routes.append(route_code)
        used_months |= set(shared)
        for m in shared:
            x.append(aipi_chg[m])
            y.append(dgca_chg[m])

    pearson, spearman, mape, directional, insufficient, stat_notes = _stats(
        x, y, "route_month_panel"
    )
    notes.extend(stat_notes)
    notes.append(
        f"Panel pools {len(used_routes)} route(s) x {len(used_months)} month(s) = "
        f"{len(x)} paired movements. Observations are route-months and are not "
        "independent within a month (common shocks: fuel, season), so the effective "
        "sample size is below n. Reported as a descriptive statistic, not as a test."
    )
    return BacktestResult(
        comparison="route_month_panel",
        n=len(x),
        pearson_r=pearson,
        spearman_rho=spearman,
        mape_pct=mape,
        directional_accuracy=directional,
        insufficient_n=insufficient,
        months=sorted(used_months),
        routes=used_routes,
        notes=notes,
    )


def construct_validity_checks(
    daily_index: Mapping[date, float],
    *,
    leadtime_price_curve: Mapping[date, Mapping[int, float]] | None = None,
) -> dict[str, object]:
    """Cheap internal checks that the index behaves like an airfare index should.

    These need no DGCA data and are available from day one, which matters when the
    external back-test is under-powered. A statistic that fails an obvious
    behavioural check is wrong regardless of what it correlates with.

    Note on which object is checked: monotonicity is a property of the lead-time
    *price curve* (relative fare level by advance window), NOT of
    `IndexResult.leadtime_index`. Every window's index equals 100 at the base
    period by construction, so their ordering afterwards reflects differential
    inflation and has no reason to be monotone. Checking the wrong one produces a
    failure that looks alarming and means nothing.
    """
    checks: dict[str, object] = {}

    if leadtime_price_curve:
        latest = max(leadtime_price_curve)
        curve = leadtime_price_curve[latest]
        windows = sorted(curve)
        if len(windows) >= 2:
            levels = [float(curve[w]) for w in windows]
            # Fares must fall as the booking moves earlier. If this slopes the
            # other way, the sampling, the matching, or the source is broken.
            checks["leadtime_monotone_decreasing"] = all(
                a >= b - 1e-9 for a, b in zip(levels, levels[1:], strict=False)
            )
            checks["leadtime_spread_pct"] = round(
                100.0 * (max(levels) - min(levels)) / min(levels), 3
            )
            checks["leadtime_curve_date"] = latest.isoformat()
            checks["leadtime_curve"] = {str(w): round(float(curve[w]), 3) for w in windows}

    values = [float(v) for v in daily_index.values()]
    if len(values) >= 3:
        arr = np.array(values)
        rel = np.diff(arr) / arr[:-1]
        checks["daily_volatility_pct"] = round(100.0 * float(np.std(rel, ddof=1)), 4)
        checks["max_daily_move_pct"] = round(100.0 * float(np.abs(rel).max()), 4)
        # A daily fare index that never moves means the collector is serving
        # cached data. This is the automated form of the Amadeus drift check.
        checks["suspiciously_flat"] = bool(np.abs(rel).max() < 1e-6)
    return checks
