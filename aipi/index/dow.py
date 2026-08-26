"""Day-of-week adjustment.

The contamination this module removes
------------------------------------
The sampling design holds ``advance_days`` fixed, so as the capture date walks
forward the *travel* date walks with it — and travel day-of-week rotates on a
weekly cycle. Friday and Sunday departures are systematically dearer than Tuesday
ones. A raw daily index therefore contains a hard weekly oscillation that is a
property of the calendar, not of inflation, and a reader looking at the raw
series will read that oscillation as volatility.

Method: classical multiplicative decomposition. Divide the index by its centred
7-day geometric moving average, average the resulting log ratios by day of week,
and normalise the seven factors to multiply to 1. Deliberately not
X-13ARIMA-SEATS: with a series this short, a seven-parameter estimate is the most
that is honestly identifiable, and a simple estimator whose every step can be
shown to a judge beats a black box that cannot be defended in the room.

Both series are published. The adjustment is disclosed, never applied silently.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, timedelta

#: Below this many observations the seven factors are not identifiable and the
#: adjustment degrades to identity rather than fitting noise.
MIN_DAYS_FOR_DOW = 21

#: A day of week needs at least this many observations to get its own factor.
MIN_OBS_PER_DOW = 2

IDENTITY_FACTORS: dict[int, float] = dict.fromkeys(range(7), 1.0)


def centred_log_ma(series: Mapping[date, float], window: int = 7) -> dict[date, float]:
    """Centred geometric moving average, in logs. Only full windows are returned."""
    half = window // 2
    out: dict[date, float] = {}
    for d in sorted(series):
        span = [d + timedelta(days=k) for k in range(-half, half + 1)]
        vals = [series.get(s) for s in span]
        if any(v is None or v <= 0 for v in vals):
            continue
        out[d] = sum(math.log(float(v)) for v in vals) / window  # type: ignore[arg-type]
    return out


def estimate_dow_factors(series: Mapping[date, float]) -> dict[int, float]:
    """Multiplicative day-of-week factors, keyed by ``date.weekday()`` (Mon=0).

    Returns identity factors when the series is too short to identify them —
    which is the honest outcome, not a failure.
    """
    if len(series) < MIN_DAYS_FOR_DOW:
        return dict(IDENTITY_FACTORS)

    ma = centred_log_ma(series)
    if not ma:
        return dict(IDENTITY_FACTORS)

    ratios: dict[int, list[float]] = {d: [] for d in range(7)}
    for d, log_ma in ma.items():
        level = series.get(d)
        if level is None or level <= 0:
            continue
        ratios[d.weekday()].append(math.log(float(level)) - log_ma)

    if any(len(v) < MIN_OBS_PER_DOW for v in ratios.values()):
        return dict(IDENTITY_FACTORS)

    log_factors = {d: sum(v) / len(v) for d, v in ratios.items()}
    # Normalise so the factors multiply to 1: adjustment moves the shape, never
    # the level.
    mean_log = sum(log_factors.values()) / 7
    return {d: math.exp(lf - mean_log) for d, lf in log_factors.items()}


def adjust_series(
    series: Mapping[date, float],
    factors: Mapping[int, float],
) -> dict[date, float]:
    """Divide out the day-of-week factor for each date."""
    out: dict[date, float] = {}
    for d, level in series.items():
        f = float(factors.get(d.weekday(), 1.0))
        out[d] = float(level) / f if f > 0 else float(level)
    return out


def dow_amplitude_pct(factors: Mapping[int, float]) -> float:
    """Peak-to-trough spread of the weekly cycle, in percent.

    The single number that tells a reader how much of the raw series' movement
    was the calendar. If this is large, publishing only a raw series would have
    been misleading.
    """
    vals = [float(v) for v in factors.values() if v > 0]
    if not vals:
        return 0.0
    return 100.0 * (max(vals) - min(vals)) / min(vals)
