"""Row-level validation contract with per-row rejection reasons.

Why this is hand-rolled rather than Pandera
-------------------------------------------
Pandera (or Great Expectations) answers "did this DataFrame pass?". A statistical
pipeline needs a different answer: "which rows were rejected, by which rule, and
why" — retained as a quarantine table, because an unexplained drop in accepted
observations is indistinguishable from a fall in fares. Reason codes per row are
the audit artefact; a boolean is not.

Each rule is a small, independently testable predicate. Adding a rule means
adding one entry to `RULES` and one test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

import pandas as pd

from aipi.basket import BRAND_FAMILY_MAP, TARGET_BRAND_FAMILY

# Ceiling for a plausible one-way domestic economy fare, in INR. Above this the
# row is almost certainly a business-cabin leak or a currency error, and it is
# quarantined for inspection rather than trimmed as an outlier — the two are
# different findings.
MAX_PLAUSIBLE_FARE = 100_000.0
#: Below this, a "fare" is a fee, a placeholder, or a parsing failure.
MIN_PLAUSIBLE_FARE = 500.0


@dataclass(frozen=True)
class Rule:
    """A validation rule. ``ok`` returns True for rows that should be ACCEPTED."""

    code: str
    description: str
    ok: Callable[[pd.DataFrame], pd.Series]


def _notnull(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(False, index=df.index)
    return df[col].notna()


def _soldout(df: pd.DataFrame) -> pd.Series:
    """Rows the collector saw in the schedule with no bookable fare.

    A sold-out observation carries no price, and that absence is *information* —
    it is the sample telling us inventory closed. Quarantining it as "missing
    total_fare" would delete the signal and understate how often the cheap bucket
    disappears. Such rows are therefore accepted, flagged, and excluded from the
    index by `pipeline.clean`; the fare-value rules below exempt them.
    """
    if "is_soldout" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["is_soldout"].fillna(False).astype(bool)


RULES: tuple[Rule, ...] = (
    Rule(
        "MISSING_TOTAL_FARE",
        "total_fare must be present unless the row is flagged sold out",
        lambda df: _notnull(df, "total_fare") | _soldout(df),
    ),
    Rule(
        "FARE_BELOW_FLOOR",
        f"total_fare must be >= {MIN_PLAUSIBLE_FARE:,.0f} INR",
        lambda df: (pd.to_numeric(df["total_fare"], errors="coerce") >= MIN_PLAUSIBLE_FARE)
        | _soldout(df),
    ),
    Rule(
        "FARE_ABOVE_CEILING",
        f"total_fare must be <= {MAX_PLAUSIBLE_FARE:,.0f} INR",
        lambda df: (pd.to_numeric(df["total_fare"], errors="coerce") <= MAX_PLAUSIBLE_FARE)
        | _soldout(df),
    ),
    Rule(
        "BAD_CURRENCY",
        "currency must be INR",
        lambda df: df.get("currency", pd.Series("INR", index=df.index)).fillna("INR") == "INR",
    ),
    Rule(
        "NEGATIVE_ADVANCE_DAYS",
        "advance_days must be >= 0",
        lambda df: pd.to_numeric(df["advance_days"], errors="coerce") >= 0,
    ),
    Rule(
        "ADVANCE_DAYS_MISMATCH",
        "advance_days must equal travel_date - capture_date",
        lambda df: _advance_days_consistent(df),
    ),
    Rule(
        "TRAVEL_BEFORE_CAPTURE",
        "travel_date must not precede capture_date",
        lambda df: _as_date(df["travel_date"]) >= _as_date(df["capture_date"]),
    ),
    Rule(
        "BAD_AIRPORT_CODE",
        "origin and destination must be 3-letter IATA codes",
        lambda df: _is_iata(df["origin"]) & _is_iata(df["destination"]),
    ),
    Rule(
        "SAME_ORIGIN_DESTINATION",
        "origin must differ from destination",
        lambda df: df["origin"] != df["destination"],
    ),
    Rule(
        "MISSING_FLIGHT_NO",
        "flight_no is required — it is half the matched-model identity",
        lambda df: _notnull(df, "flight_no") & (df["flight_no"].astype(str).str.len() > 0),
    ),
    Rule(
        "MISSING_CARRIER",
        "carrier is required",
        lambda df: _notnull(df, "carrier") & (df["carrier"].astype(str).str.len() > 0),
    ),
    Rule(
        "TAX_EXCEEDS_TOTAL",
        "taxes must not exceed total_fare",
        lambda df: _tax_within_total(df),
    ),
    Rule(
        "COMPONENTS_DO_NOT_SUM",
        "base + taxes + fees must equal total (1 INR tolerance) when all present",
        lambda df: _components_sum(df),
    ),
)


# ---------------------------------------------------------------------------
# predicates
# ---------------------------------------------------------------------------


def _as_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.date


def _is_iata(s: pd.Series) -> pd.Series:
    return s.astype(str).str.fullmatch(r"[A-Z]{3}").fillna(False)


def _advance_days_consistent(df: pd.DataFrame) -> pd.Series:
    cap = pd.to_datetime(df["capture_date"], errors="coerce")
    trv = pd.to_datetime(df["travel_date"], errors="coerce")
    implied = (trv - cap).dt.days
    stated = pd.to_numeric(df["advance_days"], errors="coerce")
    return (implied == stated).fillna(False)


def _tax_within_total(df: pd.DataFrame) -> pd.Series:
    taxes = pd.to_numeric(df.get("taxes"), errors="coerce")
    total = pd.to_numeric(df["total_fare"], errors="coerce")
    return taxes.isna() | (taxes <= total)


def _components_sum(df: pd.DataFrame) -> pd.Series:
    base = pd.to_numeric(df.get("base_fare"), errors="coerce")
    taxes = pd.to_numeric(df.get("taxes"), errors="coerce")
    fees = pd.to_numeric(df.get("fees"), errors="coerce").fillna(0.0)
    total = pd.to_numeric(df["total_fare"], errors="coerce")
    incomplete = base.isna() | taxes.isna()
    return incomplete | ((base + taxes + fees - total).abs() <= 1.0)


# ---------------------------------------------------------------------------
# brand mapping
# ---------------------------------------------------------------------------


def map_brand_family(fare_brand: object) -> str | None:
    """Map a carrier's brand label into a comparable family, or ``None``.

    ``None`` means "unrecognised brand" and the row is excluded from the index.
    It is never coerced to the target family — that would reintroduce exactly the
    unadjusted quality change the brand restriction exists to prevent.
    """
    if fare_brand is None or (isinstance(fare_brand, float) and pd.isna(fare_brand)):
        return None
    key = str(fare_brand).strip().upper()
    return BRAND_FAMILY_MAP.get(key)


def add_brand_family(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["brand_family"] = out.get("fare_brand", pd.Series(None, index=out.index)).map(
        map_brand_family
    )
    return out


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    accepted: pd.DataFrame
    quarantined: pd.DataFrame  # original rows plus a `reject_reason` column
    counts: dict[str, int]  # reason code -> rows failing it (rows can fail several)

    @property
    def accept_rate(self) -> float:
        total = len(self.accepted) + len(self.quarantined)
        return len(self.accepted) / total if total else 0.0


REQUIRED_INPUT_COLUMNS = (
    "capture_ts",
    "capture_date",
    "travel_date",
    "advance_days",
    "origin",
    "destination",
    "carrier",
    "flight_no",
    "total_fare",
)


def validate(df: pd.DataFrame) -> ValidationResult:
    """Apply every rule, splitting rows into accepted and quarantined.

    A row failing several rules is reported under all of them in ``counts`` and
    carries all reason codes in ``reject_reason``, so fixing one rule does not
    hide the others.
    """
    missing = [c for c in REQUIRED_INPUT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"raw quotes missing required columns: {missing}")
    if df.empty:
        empty = df.assign(reject_reason=pd.Series(dtype=str))
        return ValidationResult(df.copy(), empty, {})

    reasons = pd.Series([[] for _ in range(len(df))], index=df.index, dtype=object)
    counts: dict[str, int] = {}

    for rule in RULES:
        try:
            passed = rule.ok(df).reindex(df.index).fillna(False).astype(bool)
        except (KeyError, TypeError, ValueError):
            # A rule that cannot be evaluated fails closed: unevaluable data is
            # quarantined, never accepted by default.
            passed = pd.Series(False, index=df.index)
        failed = ~passed
        n = int(failed.sum())
        if n:
            counts[rule.code] = n
            for idx in df.index[failed]:
                reasons.at[idx] = [*reasons.at[idx], rule.code]

    bad = reasons.map(bool)
    quarantined = df[bad].copy()
    quarantined["reject_reason"] = reasons[bad].map(lambda codes: ",".join(codes))
    return ValidationResult(df[~bad].copy(), quarantined, counts)


def basket_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Restrict to the priced basket (see `aipi.basket`).

    Returns the kept rows and a count of exclusions by reason. Every exclusion
    here is a deliberate scope decision, not a data-quality problem, which is why
    it is counted separately from quarantine.
    """
    out = add_brand_family(df)
    excluded: dict[str, int] = {}

    def drop(mask: pd.Series, code: str) -> None:
        nonlocal out
        n = int(mask.sum())
        if n:
            excluded[code] = n
        out = out[~mask]

    if "stops" in out.columns:
        drop(pd.to_numeric(out["stops"], errors="coerce").fillna(0) > 0, "NOT_NONSTOP")
    if "is_codeshare" in out.columns:
        drop(out["is_codeshare"].fillna(False).astype(bool), "CODESHARE")
    if "cabin" in out.columns:
        drop(out["cabin"].astype(str).str.upper() != "ECONOMY", "NOT_ECONOMY")

    drop(out["brand_family"].isna(), "UNRECOGNISED_BRAND")
    drop(out["brand_family"] != TARGET_BRAND_FAMILY, "OUT_OF_BRAND_FAMILY")

    return out, excluded


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise dtypes once, so downstream stages need not defend against them."""
    out = df.copy()
    out["capture_ts"] = pd.to_datetime(out["capture_ts"], errors="coerce", utc=True)
    for col in ("capture_date", "travel_date"):
        out[col] = pd.to_datetime(out[col], errors="coerce").dt.date
    out["advance_days"] = pd.to_numeric(out["advance_days"], errors="coerce").astype("Int64")
    for col in ("base_fare", "taxes", "fees", "total_fare"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in ("origin", "destination", "carrier"):
        out[col] = out[col].astype(str).str.strip().str.upper()
    return out


def today_utc() -> date:
    return pd.Timestamp.utcnow().date()
