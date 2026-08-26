"""Best-effort generic parser for flight-search JSON payloads.

Why a generic parser exists at all
-----------------------------------
Every airline/OTA search API returns its own JSON shape, and this codebase
cannot see the real payload until someone runs it against the live site (see
`docs/SCRAPER_SETUP.md`). Shipping eleven hand-tuned parsers built against
guessed schemas would be eleven confident-looking wrong answers.

Instead, this module walks the payload for lists of dict-shaped "offer-like"
objects (looking two levels deep under common container keys such as
`results`, `flights`, `tripInfos`, `data`) and reads each candidate field
under a shortlist of common name variants (`totalFare`, `total_price`,
`priceDetail.total`, ...). It is deliberately conservative: a payload it
cannot confidently map raises `CollectionError` naming the keys it saw, rather
than emitting fabricated rows.

Calibrating a site: run the scraper once with `archive_dir` set, inspect the
archived JSON, and either (a) it already parses because the field names happen
to match the shortlist, or (b) add the site's actual key names to the
shortlists below / override `parse()` in that site's class with a precise
mapping. (b) is expected, ordinary scraper maintenance — not a sign the
approach is broken.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from aipi.collectors.errors import CollectionError
from aipi.collectors.scraper.rowbuild import num, raw_row

CONTAINER_KEYS = (
    "results", "result", "flights", "flightList", "tripInfos", "trips",
    "offers", "itineraries", "data", "searchResult", "fareList", "flightResults",
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "total": (
        "totalFare", "total_price", "totalPrice", "total_fare", "grandTotal", "fare", "price",
    ),
    "base": ("baseFare", "base_price", "basePrice", "base_fare", "baseAmount"),
    "tax": ("tax", "taxes", "taxAmount", "totalTax", "tax_amount"),
    "udf": ("udf", "udfFee", "userDevelopmentFee", "airportFee", "adf"),
    "convenience": ("convenienceFee", "convenience_fee", "bookingFee", "serviceFee"),
    "fees": ("fees", "otherCharges", "surcharges", "miscFee"),
    "carrier": ("carrier", "airline", "airlineCode", "marketingCarrier", "marketingAirline"),
    "flight_no": ("flightNo", "flightNumber", "flight_number", "flightNum"),
    "brand": ("fareBrand", "brand", "fareClass", "fareFamily", "productClass"),
    "booking_class": ("bookingClass", "rbd", "classOfService", "cabinClass"),
    "stops": ("stops", "numStops", "stopCount"),
    "codeshare": ("isCodeshare", "codeshare", "operatingDiffersFromMarketing"),
    "cabin": ("cabin", "cabinType", "travelClass"),
    "currency": ("currency", "currencyCode"),
    "soldout": ("soldOut", "isSoldOut", "unavailable"),
}


def _get_alias(d: dict, key: str) -> Any:
    for name in FIELD_ALIASES[key]:
        if name in d and d[name] not in (None, ""):
            return d[name]
        # one level of dotted nesting, e.g. priceDetail.total
        for container in ("priceDetail", "price", "fare", "priceBreakup"):
            sub = d.get(container)
            if isinstance(sub, dict) and name in sub:
                return sub[name]
    return None


def _find_offer_lists(payload: Any, depth: int = 0) -> list[list[dict]]:
    """Depth-limited search for lists of dict objects under common container keys."""
    found: list[list[dict]] = []
    if depth > 3 or not isinstance(payload, dict):
        return found
    for key, value in payload.items():
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            if key in CONTAINER_KEYS or depth > 0:
                found.append(value)
        elif isinstance(value, dict):
            found.extend(_find_offer_lists(value, depth + 1))
    return found


def generic_parse(
    payload: dict,
    *,
    origin: str,
    destination: str,
    departure: date,
    source: str,
    default_carrier: str | None,
    capture_ts: datetime | None = None,
) -> list[dict]:
    capture_ts = capture_ts or datetime.now().astimezone()
    candidates = _find_offer_lists(payload)
    if not candidates:
        raise CollectionError(
            f"{source}: no offer-like list found in payload (top-level keys: "
            f"{list(payload.keys())[:15]}). The site's JSON shape does not match "
            "any container key this parser knows; inspect the archived payload and "
            "update aipi/collectors/scraper/heuristics.py or override parse() for "
            "this site. See docs/SCRAPER_SETUP.md."
        )

    offers = max(candidates, key=len)
    rows: list[dict] = []
    advance_days = (departure - capture_ts.date()).days

    for offer in offers:
        total = num(_get_alias(offer, "total"))
        if total is None:
            continue  # not a fare-bearing object; skip rather than fabricate
        base = num(_get_alias(offer, "base"))
        tax = num(_get_alias(offer, "tax"))
        udf = num(_get_alias(offer, "udf"))
        convenience = num(_get_alias(offer, "convenience"))
        fees = num(_get_alias(offer, "fees"))
        carrier = str(_get_alias(offer, "carrier") or default_carrier or "")
        rows.append(
            raw_row(
                capture_ts=capture_ts,
                travel_date=departure,
                advance_days=advance_days,
                origin=origin,
                destination=destination,
                carrier=carrier,
                flight_no=str(_get_alias(offer, "flight_no") or ""),
                fare_brand=str(_get_alias(offer, "brand") or ""),
                booking_class=str(_get_alias(offer, "booking_class") or ""),
                cabin=str(_get_alias(offer, "cabin") or "ECONOMY").upper(),
                stops=int(num(_get_alias(offer, "stops")) or 0),
                is_codeshare=bool(_get_alias(offer, "codeshare") or False),
                base_fare=base,
                taxes=tax,
                udf_fee=udf,
                convenience_fee=convenience,
                fees=fees,
                total_fare=total,
                currency=str(_get_alias(offer, "currency") or "INR"),
                source=source,
                data_mode="real",
                is_soldout=bool(_get_alias(offer, "soldout") or False),
            )
        )

    if not rows:
        raise CollectionError(
            f"{source}: found {len(offers)} candidate objects but none carried a "
            "recognisable total-fare field. Update FIELD_ALIASES['total'] in "
            "heuristics.py with this site's actual key name."
        )
    return rows
