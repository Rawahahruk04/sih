"""Index engine.

Three levels, in this order:

  L1  elementary aggregate  — matched Jevons within (route x advance window)
  L2  window aggregation    — booking-share weighted, cells -> route
  L3  headline              — Laspeyres, EXPENDITURE weighted, routes -> India

The L1 implementation is the part that matters. See `elementary.py` for why a
geometric mean of fare *levels* is not a Jevons index, and `geks.py` for why a
chained daily Jevons is not usable at this frequency.
"""

from aipi.index.aggregate import (
    expenditure_weights,
    laspeyres_headline,
    window_aggregate,
)
from aipi.index.dow import adjust_series, estimate_dow_factors
from aipi.index.elementary import (
    chained_jevons,
    geometric_mean,
    jevons_bilateral,
    log_jevons_bilateral,
    naive_gm_level_index,
)
from aipi.index.geks import geks_jevons, rolling_geks_jevons

__all__ = [
    "adjust_series",
    "chained_jevons",
    "estimate_dow_factors",
    "expenditure_weights",
    "geks_jevons",
    "geometric_mean",
    "jevons_bilateral",
    "laspeyres_headline",
    "log_jevons_bilateral",
    "naive_gm_level_index",
    "rolling_geks_jevons",
    "window_aggregate",
]
