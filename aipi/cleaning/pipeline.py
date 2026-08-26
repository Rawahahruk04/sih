"""The cleaning pipeline. Stage order is load-bearing; see each stage's note.

Sold-out and missing fares — read this before changing anything
---------------------------------------------------------------
The PRD treats sold-out cells as an imputation problem. They are not, for the
index. A Jevons elementary aggregate drops a temporarily-missing item from the
matched pair, and *dropping an item from a Jevons link is arithmetically identical
to imputing its movement with the cell's mean movement* — which is precisely the
class-mean imputation the CPI Manual prescribes for temporarily missing prices.
The index already does the textbook thing; adding an explicit imputation step
would change nothing except adding rows that look like observations and are not.

What sold-out inventory *actually* breaks is transitivity: a fare that vanishes
while discounted and returns at full price ratchets a chained index downward.
That is chain drift, and it is fixed in `aipi.index.geks` by using a multilateral
index — structurally, not by patching the data.

So: sold-out rows are recorded and flagged for the audit trail and for the
average-fare-level series, and are excluded from index computation. They are
never valued at zero and never treated as the cheapest available fare.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import pandas as pd

from aipi.basket import (
    CAPTURE_TOLERANCE_MINUTES,
    INDEX_CAPTURE_SLOT,
    ITEM_KEY_FIELDS,
)
from aipi.cleaning.contract import (
    ValidationResult,
    basket_filter,
    coerce_types,
    validate,
)
from aipi.cleaning.decomposition import FareSplitModel, apply_fare_split, calibrate_fare_split
from aipi.cleaning.outliers import flag_outliers_log_mad, sensitivity_report

#: De-duplication identity. `flight_no` is present deliberately: a route/carrier
#: has ~20 departures a day, so a key without it collides and silently discards
#: real observations.
DEDUP_KEY = (
    "capture_date",
    "origin",
    "destination",
    "travel_date",
    "advance_days",
    "carrier",
    "flight_no",
    "brand_family",
    "booking_class",
)


@dataclass
class CleaningReport:
    """Row accounting from raw to index-eligible. Serialised to `/methodology`.

    Every stage records what it removed. An unexplained fall in accepted rows is
    indistinguishable from a fall in fares, so the accounting is part of the
    statistical output, not a debug log.
    """

    rows_in: int = 0
    rows_quarantined: int = 0
    quarantine_reasons: dict[str, int] = field(default_factory=dict)
    rows_off_capture_slot: int = 0
    basket_exclusions: dict[str, int] = field(default_factory=dict)
    rows_deduplicated: int = 0
    rows_soldout: int = 0
    split_imputation: dict[str, int] = field(default_factory=dict)
    split_model: dict = field(default_factory=dict)
    outliers: dict[str, int] = field(default_factory=dict)
    outlier_sensitivity: dict[str, float] = field(default_factory=dict)
    rows_index_eligible: int = 0

    @property
    def retention_pct(self) -> float:
        return 100.0 * self.rows_index_eligible / self.rows_in if self.rows_in else 0.0

    def to_dict(self) -> dict:
        d = {
            "rows_in": self.rows_in,
            "rows_quarantined": self.rows_quarantined,
            "quarantine_reasons": self.quarantine_reasons,
            "rows_off_capture_slot": self.rows_off_capture_slot,
            "basket_exclusions": self.basket_exclusions,
            "rows_deduplicated": self.rows_deduplicated,
            "rows_soldout": self.rows_soldout,
            "split_imputation": self.split_imputation,
            "split_model": self.split_model,
            "outliers": self.outliers,
            "outlier_sensitivity": self.outlier_sensitivity,
            "rows_index_eligible": self.rows_index_eligible,
            "retention_pct": round(self.retention_pct, 2),
        }
        return d


@dataclass
class CleanResult:
    clean_fares: pd.DataFrame  # every accepted row, flags included
    index_input: pd.DataFrame  # index-eligible subset, engine-ready
    quarantined: pd.DataFrame
    report: CleaningReport
    split_model: FareSplitModel


def clean(
    raw: pd.DataFrame,
    *,
    index_slot: time = INDEX_CAPTURE_SLOT,
    slot_tolerance_min: int = CAPTURE_TOLERANCE_MINUTES,
    min_n_for_trim: int = 8,
    mad_k: float = 3.5,
    enforce_slot: bool = True,
) -> CleanResult:
    """Raw quotes to index-eligible fares."""
    report = CleaningReport(rows_in=len(raw))
    if raw.empty:
        return CleanResult(raw.copy(), raw.copy(), raw.copy(), report, calibrate_fare_split(raw))

    # 1. Types first. Every later stage assumes normalised dtypes.
    df = coerce_types(raw)

    # 2. Validate before anything mutates the data, so quarantine reasons refer
    #    to what the source actually sent.
    result: ValidationResult = validate(df)
    report.rows_quarantined = len(result.quarantined)
    report.quarantine_reasons = dict(result.counts)
    df = result.accepted

    # 3. Route code, needed by every subsequent grouping.
    df = df.assign(route_code=df["origin"] + "-" + df["destination"])

    # 4. Capture-slot discipline. Fares move intraday, so a drifting capture time
    #    would inject collection noise into the index as if it were inflation.
    #    Off-slot rows are KEPT (they are the intraday volatility evidence) but
    #    marked ineligible.
    df = _tag_capture_slot(df, index_slot, slot_tolerance_min)
    report.rows_off_capture_slot = int((~df["in_index_slot"]).sum())

    # 5. Basket restriction: non-stop, economy, single brand family, no codeshare.
    df, exclusions = basket_filter(df)
    report.basket_exclusions = exclusions

    # 6. De-duplicate. Latest capture wins; ties break to the lower fare, since a
    #    duplicate pair usually means the same offer seen twice mid-refresh.
    before = len(df)
    df = _dedupe(df)
    report.rows_deduplicated = before - len(df)

    # 7. Fare decomposition, calibrated on the rows that have a real breakdown.
    model = calibrate_fare_split(df)
    df, split_counts = apply_fare_split(df, model)
    report.split_imputation = split_counts
    report.split_model = model.to_dict()

    # 8. Sold-out flagging. Recorded, excluded from the index, never valued.
    if "is_soldout" not in df.columns:
        df["is_soldout"] = False
    df["is_soldout"] = df["is_soldout"].fillna(False).astype(bool)
    report.rows_soldout = int(df["is_soldout"].sum())

    # 9. Outliers: flagged, never deleted.
    df, outlier_summary = flag_outliers_log_mad(df, min_n=min_n_for_trim, k=mad_k)
    report.outliers = outlier_summary
    report.outlier_sensitivity = sensitivity_report(df, min_n=min_n_for_trim)

    # 10. Matched-model identity.
    df = _add_item_key(df)

    # 11. Index-eligible subset.
    eligible = ~df["outlier_flag"] & ~df["is_soldout"]
    if enforce_slot:
        eligible &= df["in_index_slot"]
    index_input = df[eligible][
        ["capture_date", "route_code", "advance_days", "item_key", "total_fare"]
    ].copy()
    index_input["advance_days"] = index_input["advance_days"].astype(int)
    index_input["total_fare"] = index_input["total_fare"].astype(float)
    report.rows_index_eligible = len(index_input)

    return CleanResult(df, index_input, result.quarantined, report, model)


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------


def _tag_capture_slot(df: pd.DataFrame, slot: time, tolerance_min: int) -> pd.DataFrame:
    """Mark rows captured within tolerance of the index slot (IST)."""
    out = df.copy()
    ts_ist = pd.to_datetime(out["capture_ts"], utc=True, errors="coerce").dt.tz_convert(
        "Asia/Kolkata"
    )
    minutes = ts_ist.dt.hour * 60 + ts_ist.dt.minute
    target = slot.hour * 60 + slot.minute
    # Circular distance, so a 00:15 slot matches a 23:55 capture.
    delta = (minutes - target).abs()
    delta = pd.concat([delta, 1440 - delta], axis=1).min(axis=1)
    out["capture_minutes_ist"] = minutes
    out["in_index_slot"] = (delta <= tolerance_min).fillna(False)
    return out


def _dedupe(df: pd.DataFrame) -> pd.DataFrame:
    keys = [k for k in DEDUP_KEY if k in df.columns]
    out = df.sort_values(["capture_ts", "total_fare"], ascending=[False, True])
    out = out.drop_duplicates(subset=keys, keep="first")
    return out.sort_index()


def _add_item_key(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for field_name in ITEM_KEY_FIELDS:
        if field_name not in out.columns:
            out[field_name] = "NA"
    out["item_key"] = (
        out[list(ITEM_KEY_FIELDS)].astype(str).apply(lambda r: "|".join(r), axis=1)
    )
    return out
