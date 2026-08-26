"""Shared row-shaping helper for site scrapers.

Every site's JSON is shaped differently; what must not vary is the output
contract. `raw_row()` fills every RAW_COLUMNS field with an explicit value or
an explicit null — never a silently-omitted key — so a scraper's `parse()`
cannot accidentally under-report a column and have it fail closed only much
later, inside `aipi.cleaning.contract.validate`.
"""

from __future__ import annotations

from datetime import date, datetime

from aipi.collectors.synthetic import RAW_COLUMNS


def raw_row(
    *,
    capture_ts: datetime,
    travel_date: date,
    advance_days: int,
    origin: str,
    destination: str,
    carrier: str,
    flight_no: str,
    fare_brand: str,
    booking_class: str,
    cabin: str,
    stops: int,
    is_codeshare: bool,
    base_fare: float | None,
    taxes: float | None,
    fees: float | None,
    total_fare: float | None,
    currency: str,
    source: str,
    udf_fee: float | None = None,
    convenience_fee: float | None = None,
    data_mode: str = "real",
    is_soldout: bool = False,
) -> dict:
    row = {
        "capture_ts": capture_ts,
        "capture_date": capture_ts.date(),
        "travel_date": travel_date,
        "advance_days": int(advance_days),
        "origin": origin,
        "destination": destination,
        "carrier": carrier,
        "flight_no": flight_no,
        "fare_brand": fare_brand,
        "booking_class": booking_class,
        "cabin": cabin,
        "stops": int(stops),
        "is_codeshare": bool(is_codeshare),
        "base_fare": base_fare,
        "taxes": taxes,
        "udf_fee": udf_fee,
        "convenience_fee": convenience_fee,
        "fees": fees,
        "total_fare": total_fare,
        "currency": currency,
        "source": source,
        "data_mode": data_mode,
        "is_soldout": bool(is_soldout),
    }
    assert set(row) == set(RAW_COLUMNS), "raw_row() drifted from RAW_COLUMNS"
    return row


def num(value: object) -> float | None:
    """Best-effort numeric coercion for fare fields pulled out of arbitrary JSON."""
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
