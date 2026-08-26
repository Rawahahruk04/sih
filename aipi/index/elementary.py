"""Level 1 — the elementary aggregate.

The distinction this module exists to enforce
--------------------------------------------
There are two things people call "the geometric mean elementary index", and they
are not the same:

  (a) Jevons:  GM over items of the PRICE RELATIVES   p_i,t / p_i,s
  (b) "GM of levels":  GM(prices at t)  /  GM(prices at s)

(a) == (b) if and only if the item set is IDENTICAL in both periods. Airline
schedules churn every day — flights get added, cancelled, sold out, retimed — so
the item set is never identical, and (b) therefore mixes genuine price change
with *composition* change. If a cheap early-morning flight simply stops
operating, (b) records inflation that no consumer paid.

CPI's elementary aggregate is (a). This module implements (a), and also
implements (b) as `naive_gm_level_index` so the composition bias can be
*measured and reported* rather than argued about. Publishing the gap between
them is a stronger claim than asserting the right one was used.

Terminology note: within a cell all items are the same product spec (same route,
same advance window, same brand family), so no quantity weights exist at this
level. That is exactly the situation Jevons is for.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date

#: A period's prices inside one cell: item_key -> price.
PriceVector = Mapping[str, float]
#: A cell's full history: period -> PriceVector.
Panel = Mapping[date, PriceVector]


def geometric_mean(values: Sequence[float]) -> float:
    """Geometric mean, computed in log space to avoid overflow on long products.

    Raises on non-positive input: a zero or negative fare is a data error, not a
    price. Silently dropping it would hide a collection bug.
    """
    if not values:
        raise ValueError("geometric_mean of empty sequence")
    if any(v <= 0 for v in values):
        raise ValueError(f"non-positive fare in elementary aggregate: {values!r}")
    return math.exp(sum(math.log(v) for v in values) / len(values))


def matched_items(prices_s: PriceVector, prices_t: PriceVector) -> list[str]:
    """Items priced in BOTH periods — the matched-model sample."""
    return sorted(set(prices_s) & set(prices_t))


def log_jevons_bilateral(
    prices_s: PriceVector,
    prices_t: PriceVector,
    min_matched: int = 2,
) -> float | None:
    """log of the Jevons price index from period s to period t.

    Returns ``None`` when fewer than ``min_matched`` items are common to both
    periods. ``None`` means "not estimable", which is different from 1.0
    ("no change") — conflating the two is how sparse cells fabricate stability.
    """
    common = matched_items(prices_s, prices_t)
    if len(common) < min_matched:
        return None
    total = 0.0
    for k in common:
        p_s, p_t = prices_s[k], prices_t[k]
        if p_s <= 0 or p_t <= 0:
            raise ValueError(f"non-positive fare for item {k}: {p_s} -> {p_t}")
        total += math.log(p_t / p_s)
    return total / len(common)


def jevons_bilateral(
    prices_s: PriceVector,
    prices_t: PriceVector,
    min_matched: int = 2,
) -> float | None:
    """Jevons price index s -> t. 1.0 means no change. ``None`` if not estimable."""
    lg = log_jevons_bilateral(prices_s, prices_t, min_matched)
    return None if lg is None else math.exp(lg)


def naive_gm_level_index(panel: Panel, *, base: float = 100.0) -> dict[date, float]:
    """The WRONG elementary index, implemented deliberately.

    Ratio of the geometric mean of fare *levels* to the base period's. Retained
    only to quantify composition bias against `chained_jevons` / GEKS — never
    published as the headline.
    """
    periods = sorted(panel)
    if not periods:
        return {}
    anchor = geometric_mean(list(panel[periods[0]].values()))
    return {p: base * geometric_mean(list(panel[p].values())) / anchor for p in periods}


def chained_jevons(
    panel: Panel,
    *,
    base: float = 100.0,
    min_matched: int = 2,
) -> dict[date, float]:
    """Day-on-day chained matched Jevons.

    Correct at each individual link and the natural fix for a churning item set —
    but subject to CHAIN DRIFT at daily frequency. See `geks.py`. Retained as the
    documented comparison series, and as the thing whose drift the GEKS variant
    is shown to remove.

    A non-estimable link carries the index forward unchanged and is reported in
    the returned diagnostics via `chained_jevons_with_gaps`.
    """
    series, _ = chained_jevons_with_gaps(panel, base=base, min_matched=min_matched)
    return series


def chained_jevons_with_gaps(
    panel: Panel,
    *,
    base: float = 100.0,
    min_matched: int = 2,
) -> tuple[dict[date, float], list[date]]:
    """As `chained_jevons`, plus the list of periods whose link was not estimable."""
    periods = sorted(panel)
    if not periods:
        return {}, []
    out: dict[date, float] = {periods[0]: base}
    gaps: list[date] = []
    level = base
    for prev, cur in zip(periods, periods[1:], strict=False):
        link = jevons_bilateral(panel[prev], panel[cur], min_matched)
        if link is None:
            gaps.append(cur)
        else:
            level *= link
        out[cur] = level
    return out, gaps


def cell_observation_counts(panel: Panel) -> dict[date, int]:
    """Items priced per period. Every published index value ships with its n."""
    return {p: len(v) for p, v in panel.items()}


def matched_sample_sizes(panel: Panel) -> dict[date, int]:
    """Matched-item count for each day-on-day link — the effective sample size.

    This, not the raw observation count, is what the index is actually estimated
    from, and it is the number a statistician will ask for.
    """
    periods = sorted(panel)
    out: dict[date, int] = {}
    for prev, cur in zip(periods, periods[1:], strict=False):
        out[cur] = len(matched_items(panel[prev], panel[cur]))
    if periods:
        out.setdefault(periods[0], len(panel[periods[0]]))
    return out
