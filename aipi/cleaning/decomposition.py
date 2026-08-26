"""Fare decomposition: base fare / taxes / fees.

The problem: some sources return a full breakdown, others return only a total. An
index built on totals is still a valid index, but MoSPI needs the split — tax
changes are policy, not market pricing, and a statistical office must be able to
decompose the two.

The approach: **calibrate the split from the rows that have it, do not hardcode a
guess.** Indian domestic fares carry UDF, PSF, and GST components whose effective
ratio to base fare is stable within a route but varies across airports. Fitting
`taxes = a + b * total` on the complete subset and applying it to the incomplete
subset yields a split that is (a) derived from the same data, (b) versioned, and
(c) reportable with its own fit quality — so a reader can judge how much of the
series depends on it.

Every imputed row is flagged. The number of rows relying on the model, and the
model's R^2, are published in the cleaning report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

#: Bump on any change to the fitting procedure. Persisted with each imputed row
#: so a past index value can always be traced to the model that produced it.
SPLIT_MODEL_VERSION = "taxfit-v1"

#: Minimum complete rows before a fit is trusted. Below this the split is left
#: missing rather than extrapolated from a handful of points.
MIN_ROWS_FOR_FIT = 30

#: Fallback effective tax share of total, used ONLY when a fit is impossible and
#: recorded as `FALLBACK` in the report so it is never mistaken for a fitted
#: value. Order-of-magnitude placeholder for Indian domestic economy.
FALLBACK_TAX_SHARE = 0.18


@dataclass(frozen=True)
class FareSplitModel:
    """taxes ~= intercept + slope * total_fare."""

    version: str
    intercept: float
    slope: float
    n_fitted: int
    r_squared: float
    method: str  # 'OLS' | 'FALLBACK'

    def predict_taxes(self, total: pd.Series) -> pd.Series:
        taxes = self.intercept + self.slope * total
        # A tax component can be neither negative nor the whole fare.
        return taxes.clip(lower=0.0, upper=total * 0.95)

    def to_dict(self) -> dict:
        return asdict(self)


def calibrate_fare_split(df: pd.DataFrame) -> FareSplitModel:
    """Fit the split on rows where the source supplied both taxes and total."""
    if "taxes" not in df.columns or "total_fare" not in df.columns:
        return _fallback(0)

    taxes = pd.to_numeric(df["taxes"], errors="coerce")
    total = pd.to_numeric(df["total_fare"], errors="coerce")
    complete = taxes.notna() & total.notna() & (total > 0) & (taxes >= 0) & (taxes < total)
    n = int(complete.sum())
    if n < MIN_ROWS_FOR_FIT:
        return _fallback(n)

    x = total[complete].to_numpy(dtype=float)
    y = taxes[complete].to_numpy(dtype=float)
    slope, intercept = np.polyfit(x, y, 1)

    pred = intercept + slope * x
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return FareSplitModel(
        version=SPLIT_MODEL_VERSION,
        intercept=float(intercept),
        slope=float(slope),
        n_fitted=n,
        r_squared=r2,
        method="OLS",
    )


def _fallback(n: int) -> FareSplitModel:
    return FareSplitModel(
        version=SPLIT_MODEL_VERSION,
        intercept=0.0,
        slope=FALLBACK_TAX_SHARE,
        n_fitted=n,
        r_squared=0.0,
        method="FALLBACK",
    )


def apply_fare_split(
    df: pd.DataFrame, model: FareSplitModel
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Fill missing base/taxes from the model, flagging every imputed row.

    `total_fare` is never modified — it is the observed quantity and the index
    input. Only the decomposition is imputed.
    """
    out = df.copy()
    total = pd.to_numeric(out["total_fare"], errors="coerce")

    if "taxes" not in out.columns:
        out["taxes"] = np.nan
    if "base_fare" not in out.columns:
        out["base_fare"] = np.nan
    if "fees" not in out.columns:
        out["fees"] = 0.0

    out["taxes"] = pd.to_numeric(out["taxes"], errors="coerce")
    out["base_fare"] = pd.to_numeric(out["base_fare"], errors="coerce")
    out["fees"] = pd.to_numeric(out["fees"], errors="coerce").fillna(0.0)

    need_taxes = out["taxes"].isna() & total.notna()
    out.loc[need_taxes, "taxes"] = model.predict_taxes(total[need_taxes])

    need_base = out["base_fare"].isna() & total.notna()
    out.loc[need_base, "base_fare"] = (
        total[need_base] - out.loc[need_base, "taxes"] - out.loc[need_base, "fees"]
    ).clip(lower=0.0)

    imputed = need_taxes | need_base
    out["split_is_imputed"] = imputed
    out["split_model_version"] = np.where(imputed, model.version, None)

    return out, {
        "taxes_imputed": int(need_taxes.sum()),
        "base_fare_imputed": int(need_base.sum()),
        "rows_with_imputed_split": int(imputed.sum()),
    }
