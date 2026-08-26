"""Rolling-window GEKS-Jevons — the drift-free elementary index.

Why this module exists
----------------------
A chained daily Jevons is correct at every individual link and still wrong over
a span, because of **chain drift**: when an item leaves the sample while its
price is temporarily low and returns at its normal price, the downward link is
recorded and the offsetting upward link is not (the item was unmatched at the
moment it recovered). The index ratchets. This is the central, well-documented
pathology of high-frequency price data in the scanner-data literature, and daily
airfare — where inventory buckets open and close constantly — is the same
problem class, only worse.

The standard remedy is a **multilateral** index: instead of walking period to
period, compare every period with every other and reconcile. GEKS
(Gini–Éltető–Köves–Szulc) does this and is *transitive by construction*, so it
cannot drift.

  P_GEKS(s,t) = prod over l in window of [ P(s,l) * P(l,t) ] ^ (1/T)

with P a bilateral index — here Jevons, because no quantity weights exist at the
elementary level (all items in a cell share one product spec).

Implementation note worth reading
---------------------------------
Taking logs, and using antisymmetry ln P(s,l) = -ln P(l,s):

  ln P_GEKS(s,t) = mean_l[ln P(l,t)] - mean_l[ln P(l,s)]

So GEKS collapses to a **difference of column means of the log-bilateral
matrix** — O(T^2) to build, O(T) to read, and transitivity is then obvious by
inspection rather than by proof. `tests/test_geks.py` asserts it.

Rolling window + splice
-----------------------
GEKS over an ever-growing window would revise history every day, which a
statistical consumer cannot accept. The published series is therefore built with
a fixed-length rolling window and a **movement splice**: each new day extends the
published series by the newest window's own last movement. Earlier published
values are never revised.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date

import numpy as np

from aipi.index.elementary import Panel, log_jevons_bilateral


def log_bilateral_matrix(
    panel: Panel,
    periods: list[date],
    *,
    min_matched: int = 2,
) -> np.ndarray:
    """Antisymmetric T x T matrix of ln P_Jevons(periods[i], periods[j]).

    ``NaN`` marks a pair with too few matched items to estimate. NaNs are
    tolerated (they are averaged around) but tracked — a cell where most pairs
    are NaN is not producing an index, and `geks_coverage` reports that.
    """
    t = len(periods)
    m = np.full((t, t), np.nan, dtype=float)
    np.fill_diagonal(m, 0.0)
    for i in range(t):
        for j in range(i + 1, t):
            lg = log_jevons_bilateral(panel[periods[i]], panel[periods[j]], min_matched)
            if lg is not None:
                m[i, j] = lg
                m[j, i] = -lg
    return m


def geks_coverage(matrix: np.ndarray) -> float:
    """Fraction of off-diagonal period pairs that were estimable."""
    t = matrix.shape[0]
    off = t * t - t
    if off == 0:
        return 1.0
    return float(np.count_nonzero(~np.isnan(matrix)) - t) / off


def geks_jevons(
    panel: Panel,
    *,
    base: float = 100.0,
    min_matched: int = 2,
) -> dict[date, float]:
    """Full-window GEKS-Jevons, normalised so the first period equals ``base``.

    Transitive and drift-free. Use `rolling_geks_jevons` for the published
    series; this is the correct primitive and the right thing to unit-test.
    """
    periods = sorted(panel)
    if not periods:
        return {}
    if len(periods) == 1:
        return {periods[0]: base}

    matrix = log_bilateral_matrix(panel, periods, min_matched=min_matched)
    # Column means over available pairs: m(t) = mean_l ln P(l, t).
    with np.errstate(invalid="ignore"):
        col_mean = np.nanmean(matrix, axis=0)
    col_mean = np.nan_to_num(col_mean, nan=0.0)

    log_rel = col_mean - col_mean[0]
    return {p: base * math.exp(float(log_rel[i])) for i, p in enumerate(periods)}


def rolling_geks_jevons(
    panel: Panel,
    *,
    window: int = 25,
    base: float = 100.0,
    min_matched: int = 2,
) -> dict[date, float]:
    """Published elementary series: fixed-window GEKS with a movement splice.

    Guarantees:
      * no revision of already-published values,
      * no chain drift within the window,
      * bounded compute as the series grows.
    """
    periods = sorted(panel)
    if len(periods) <= window:
        return geks_jevons(panel, base=base, min_matched=min_matched)

    out = dict(
        geks_jevons(
            {p: panel[p] for p in periods[:window]}, base=base, min_matched=min_matched
        )
    )

    for end in range(window, len(periods)):
        win = periods[end - window + 1 : end + 1]
        g = geks_jevons({p: panel[p] for p in win}, base=base, min_matched=min_matched)
        prev_p, cur_p = win[-2], win[-1]
        prev_level = g.get(prev_p)
        cur_level = g.get(cur_p)
        if not prev_level or not cur_level:
            out[cur_p] = out[prev_p]
            continue
        out[cur_p] = out[prev_p] * (cur_level / prev_level)

    return out


def drift_diagnostic(
    chained: Mapping[date, float],
    geks: Mapping[date, float],
) -> dict[str, float]:
    """Quantify how much chain drift GEKS removed.

    Reported in the submission as evidence the multilateral method was necessary
    rather than decorative.
    """
    common = sorted(set(chained) & set(geks))
    if len(common) < 2:
        return {"n": float(len(common)), "max_abs_gap_pct": 0.0, "end_gap_pct": 0.0}
    gaps = [100.0 * (chained[p] - geks[p]) / geks[p] for p in common]
    return {
        "n": float(len(common)),
        "max_abs_gap_pct": max(abs(g) for g in gaps),
        "end_gap_pct": gaps[-1],
    }
