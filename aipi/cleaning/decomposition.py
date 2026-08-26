"""Fare decomposition: base fare / taxes / UDF / convenience charge / residual.

PS 26056 requires base fare to be separated from "taxes, user development fee
and convenience charges" — four identified components, not two.

The problem: some sources return a full breakdown, others return only a total. An
index built on totals is still a valid index, but MoSPI needs the split — tax
changes are policy, not market pricing, and a statistical office must be able to
decompose the two.

Two different imputation strategies, because the components behave differently
-------------------------------------------------------------------------------
**Taxes are ad-valorem**, so they scale with the fare and are fitted:
`taxes = a + b * total` on the complete subset, applied to the incomplete one.
The fit is derived from the same data, versioned, and reported with its R² so a
reader can judge how much of the series depends on it.

**UDF is a fixed per-departure charge set by the airport operator**, not a
percentage. Fitting it against total fare — or folding it into the ad-valorem tax
regression — would make a constant charge appear to rise whenever fares rise,
manufacturing inflation out of a fee that did not change. It is therefore imputed
from a published per-airport schedule keyed on origin, and flagged separately.

**Convenience charges are levied by OTAs, not by airlines.** A missing value on
an airline-direct source is a true zero; on an OTA it is genuinely unknown. The
two are distinguished by `source` rather than both being filled with the same
number.

Every imputed row is flagged, per component. The counts are published in the
cleaning report.
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

#: User Development Fee per departing domestic passenger, in INR, by origin
#: airport. PLACEHOLDER SCHEDULE — order-of-magnitude figures pending the
#: AERA-notified tariff order for each airport. Replace before publication and
#: bump `UDF_SCHEDULE_VERSION`.
#:
#: Keyed on ORIGIN only: UDF is charged on departure, so a DEL-BOM passenger pays
#: Delhi's UDF regardless of destination.
UDF_SCHEDULE: dict[str, float] = {
    "DEL": 236.0,
    "BOM": 187.0,
    "BLR": 306.0,
    "MAA": 214.0,
    "CCU": 193.0,
    "HYD": 281.0,
    "GOI": 168.0,
    "GAU": 154.0,
}
UDF_SCHEDULE_VERSION = "udf-placeholder-v1"
#: Applied when an origin is absent from the schedule. Flagged as imputed.
DEFAULT_UDF = 200.0

#: Sources that levy a convenience charge. An airline's own website does not;
#: aggregators do. A null on a non-levying source is a true zero, not a gap.
OTA_SOURCES = frozenset(
    {"makemytrip", "yatra", "easemytrip", "cleartrip", "ixigo", "goibibo"}
)
#: Placeholder OTA convenience charge, INR per passenger, used when the source
#: levies one but did not itemise it.
DEFAULT_CONVENIENCE_FEE = 249.0


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


def impute_udf(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """UDF from the published per-airport schedule, keyed on origin.

    Returns (values, was_imputed). Deliberately NOT fitted against total_fare:
    UDF is a fixed statutory charge, and an ad-valorem imputation would make it
    grow with the fare — inventing inflation in a component that did not move.
    """
    if "udf_fee" in df.columns:
        existing = pd.to_numeric(df["udf_fee"], errors="coerce")
    else:
        existing = pd.Series(np.nan, index=df.index)

    origin = df.get("origin", pd.Series("", index=df.index)).astype(str).str.upper()
    scheduled = origin.map(UDF_SCHEDULE).fillna(DEFAULT_UDF)

    need = existing.isna()
    values = existing.copy()
    values.loc[need] = scheduled.loc[need]
    return values, need


def impute_convenience_fee(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Convenience charge, imputed only for sources that actually levy one.

    On an airline's own site a missing convenience charge is a true zero and is
    filled as such without a flag — imputing a fee that the seller does not
    charge would overstate what the traveller paid.
    """
    if "convenience_fee" in df.columns:
        existing = pd.to_numeric(df["convenience_fee"], errors="coerce")
    else:
        existing = pd.Series(np.nan, index=df.index)

    source = df.get("source", pd.Series("", index=df.index)).astype(str).str.lower()
    levies = source.isin(OTA_SOURCES)

    values = existing.copy()
    need_ota = existing.isna() & levies
    values.loc[need_ota] = DEFAULT_CONVENIENCE_FEE
    values.loc[existing.isna() & ~levies] = 0.0  # true zero, not an imputation
    return values, need_ota


def apply_fare_split(
    df: pd.DataFrame, model: FareSplitModel
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Fill the missing decomposition, flagging every imputed component.

    `total_fare` is never modified — it is the observed quantity and the index
    input. Only the decomposition is imputed, and base_fare is always the
    RESIDUAL so the four components reconcile to the observed total exactly.
    """
    out = df.copy()
    total = pd.to_numeric(out["total_fare"], errors="coerce")

    for col in ("taxes", "base_fare"):
        if col not in out.columns:
            out[col] = np.nan
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if "fees" not in out.columns:
        out["fees"] = 0.0
    out["fees"] = pd.to_numeric(out["fees"], errors="coerce").fillna(0.0)

    # --- fixed and source-conditional components first --------------------
    out["udf_fee"], udf_imputed = impute_udf(out)
    out["convenience_fee"], conv_imputed = impute_convenience_fee(out)

    # --- ad-valorem taxes from the fitted model ---------------------------
    need_taxes = out["taxes"].isna() & total.notna()
    out.loc[need_taxes, "taxes"] = model.predict_taxes(total[need_taxes])

    # --- base fare as the residual ----------------------------------------
    # Recomputed for every row whose base was missing, so the identity
    # base + taxes + udf + convenience + fees == total holds by construction
    # rather than by luck.
    need_base = out["base_fare"].isna() & total.notna()
    out.loc[need_base, "base_fare"] = (
        total[need_base]
        - out.loc[need_base, "taxes"]
        - out.loc[need_base, "udf_fee"]
        - out.loc[need_base, "convenience_fee"]
        - out.loc[need_base, "fees"]
    ).clip(lower=0.0)

    imputed = need_taxes | need_base | udf_imputed | conv_imputed
    out["split_is_imputed"] = imputed
    out["split_model_version"] = np.where(imputed, model.version, None)
    out["udf_schedule_version"] = np.where(udf_imputed, UDF_SCHEDULE_VERSION, None)

    return out, {
        "taxes_imputed": int(need_taxes.sum()),
        "base_fare_imputed": int(need_base.sum()),
        "udf_imputed": int(udf_imputed.sum()),
        "convenience_fee_imputed": int(conv_imputed.sum()),
        "rows_with_imputed_split": int(imputed.sum()),
    }
