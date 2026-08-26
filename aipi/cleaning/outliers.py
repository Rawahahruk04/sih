"""Outlier detection for fare cells.

Two departures from the obvious approach, both forced by the data
----------------------------------------------------------------
1. **Trim in log space, using median/MAD — not IQR on levels.** Fare
   distributions are right-skewed and multiplicative. On levels, a symmetric rule
   trims the expensive tail far more readily than the cheap one, which biases the
   elementary aggregate downward exactly when fares spike — i.e. it suppresses
   the signal the index exists to measure.

2. **Pool over time within a cell, and refuse to trim tiny cells.** A same-day
   cell often holds 3–6 fares. IQR or percentile trimming on n=4 is not
   robustness, it is deleting a quarter of the evidence on the strength of the
   other three points. Below `min_n` no trimming happens and that fact is
   reported.

Outliers are **flagged, never deleted**. The row stays in `clean_fares` with
`outlier_flag = true` and is excluded from the index. Deleting it would break the
audit trail from `raw_quotes` and make the exclusion invisible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

#: MAD -> sigma consistency factor for a normal distribution.
MAD_TO_SIGMA = 1.4826

CELL_KEYS = ("route_code", "advance_days")


def flag_outliers_log_mad(
    df: pd.DataFrame,
    *,
    min_n: int = 8,
    k: float = 3.5,
    fare_col: str = "total_fare",
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Flag fares more than ``k`` robust sigmas from their cell's log median.

    The cell distribution is pooled across all capture dates in the cell, so the
    threshold reflects what that route/window normally costs rather than what it
    cost today.

    Returns the frame with `outlier_flag` and `outlier_z` columns, plus a summary.
    """
    out = df.copy()
    out["outlier_flag"] = False
    out["outlier_z"] = np.nan

    summary = {"cells": 0, "cells_skipped_small_n": 0, "flagged": 0}
    if out.empty:
        return out, summary

    log_fare = np.log(pd.to_numeric(out[fare_col], errors="coerce"))

    for _, idx in out.groupby(list(CELL_KEYS), dropna=False).groups.items():
        summary["cells"] += 1
        cell = log_fare.loc[idx].dropna()
        if len(cell) < min_n:
            summary["cells_skipped_small_n"] += 1
            continue

        median = float(cell.median())
        mad = float((cell - median).abs().median())
        if mad <= 0:
            # Degenerate spread (identical fares). Any deviation is either exact
            # or unmeasurable; flagging on it would be arbitrary.
            continue

        sigma = MAD_TO_SIGMA * mad
        z = (cell - median) / sigma
        out.loc[z.index, "outlier_z"] = z
        flagged = z.abs() > k
        out.loc[flagged[flagged].index, "outlier_flag"] = True
        summary["flagged"] += int(flagged.sum())

    return out, summary


def flag_outliers_iqr(
    df: pd.DataFrame,
    *,
    min_n: int = 8,
    whisker: float = 1.5,
    fare_col: str = "total_fare",
) -> tuple[pd.DataFrame, dict[str, int]]:
    """IQR alternative on fare levels, retained for sensitivity analysis only.

    Reporting how many rows each rule flags — and that the headline barely moves
    between them — is what turns "we trimmed outliers" into a defended choice.
    """
    out = df.copy()
    out["outlier_flag_iqr"] = False
    summary = {"cells": 0, "cells_skipped_small_n": 0, "flagged": 0}
    if out.empty:
        return out, summary

    fares = pd.to_numeric(out[fare_col], errors="coerce")

    for _, idx in out.groupby(list(CELL_KEYS), dropna=False).groups.items():
        summary["cells"] += 1
        cell = fares.loc[idx].dropna()
        if len(cell) < min_n:
            summary["cells_skipped_small_n"] += 1
            continue
        q1, q3 = cell.quantile(0.25), cell.quantile(0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo, hi = q1 - whisker * iqr, q3 + whisker * iqr
        flagged = (cell < lo) | (cell > hi)
        out.loc[flagged[flagged].index, "outlier_flag_iqr"] = True
        summary["flagged"] += int(flagged.sum())

    return out, summary


def sensitivity_report(df: pd.DataFrame, **kwargs) -> dict[str, float]:
    """Compare the two rules on the same data. Published, not just computed."""
    mad, mad_sum = flag_outliers_log_mad(df, **kwargs)
    iqr, iqr_sum = flag_outliers_iqr(df, **kwargs)
    n = len(df)
    return {
        "n_rows": float(n),
        "log_mad_flagged": float(mad_sum["flagged"]),
        "iqr_flagged": float(iqr_sum["flagged"]),
        "log_mad_pct": 100.0 * mad_sum["flagged"] / n if n else 0.0,
        "iqr_pct": 100.0 * iqr_sum["flagged"] / n if n else 0.0,
        "cells_untrimmed_small_n": float(mad_sum["cells_skipped_small_n"]),
        "agreement_rows": float(
            int((mad["outlier_flag"] & iqr["outlier_flag_iqr"]).sum())
        ),
    }
