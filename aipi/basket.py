"""The observation unit and the priced basket.

Nothing else in this codebase is meaningful until this module is read. A price
index is undefined unless the thing being priced is defined exactly, and
"airfare" is not a thing — it is a family of differently-specified products.

Every constant here is a methodological commitment that must be reported in the
submission. Changing any of them changes the index and requires a new
`weight_version` / base period.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

# ---------------------------------------------------------------------------
# The observation unit
# ---------------------------------------------------------------------------

#: One observation is the price of ONE seat under exactly these conditions.
OBSERVATION_UNIT = {
    "passengers": "1 adult",
    "trip_type": "one-way",
    "itinerary": "non-stop only",
    "cabin": "economy",
    "fare_selection": "lowest available fare per flight number, within the brand family",
    "price_basis": "total payable per passenger, inclusive of taxes and statutory fees",
    "currency": "INR",
    "excludes": "codeshare duplicates, refundable/flexi brands, seat/bag/meal ancillaries",
}

#: Why non-stop only: connecting itineraries price off a different inventory
#: surface (through-fares, interline proration) and their lead-time dynamics
#: differ materially. Mixing them injects variance that is not inflation.
NONSTOP_ONLY = True

#: Why codeshares are excluded: the same physical departure sold under two
#: marketing carrier codes would otherwise enter the elementary aggregate twice,
#: silently double-weighting one flight.
EXCLUDE_CODESHARE = True


# ---------------------------------------------------------------------------
# Fare brand family — the quality-adjustment control
# ---------------------------------------------------------------------------

#: Indian carriers sell branded fares (IndiGo Saver/Flexi, Air India
#: Comfort/Flex, Akasa Value/Flex ...). Comparing a Saver on day t to a Flexi on
#: day t+1 is an UNADJUSTED QUALITY CHANGE, not a price movement. The index is
#: therefore restricted to a single brand family, and the brand is persisted so
#: the restriction is auditable rather than assumed.
TARGET_BRAND_FAMILY = "SAVER"

#: Carrier-specific brand labels that map into the target family. Anything not
#: listed is dropped from the index (and logged), never silently coerced.
BRAND_FAMILY_MAP: dict[str, str] = {
    # IndiGo
    "SAVER": "SAVER",
    "6E SAVER": "SAVER",
    "FLEXI": "FLEX",
    "6E FLEX": "FLEX",
    # Air India / AIX
    "COMFORT": "SAVER",
    "VALUE": "SAVER",
    "FLEX": "FLEX",
    # Akasa / SpiceJet / generic GDS
    "ECOSAVER": "SAVER",
    "SPICESAVER": "SAVER",
    "ECONOMY": "SAVER",  # bare-economy GDS response with no brand signal
}

#: Baggage entitlement the target family must include, so the priced product is
#: constant. A "hand-baggage-only" fare and a "15kg-included" fare are different
#: products at the same nominal price.
REQUIRED_BAGGAGE = "hand baggage included; checked baggage NOT required"


# ---------------------------------------------------------------------------
# Sampling design
# ---------------------------------------------------------------------------

#: Advance-purchase windows, in days to departure. These are the elementary
#: strata: an index is only ever computed WITHIN a window, never across.
ADVANCE_WINDOWS: tuple[int, ...] = (1, 3, 7, 14, 21, 30, 60)

#: Fares move intraday. If the capture time drifts, the resulting variance is
#: collection noise entering the index as if it were inflation. Exactly ONE slot
#: per day feeds the index; additional slots are collected for the intraday
#: volatility evidence but are excluded from index computation.
INDEX_CAPTURE_SLOT = time(6, 30)  # IST
AUXILIARY_CAPTURE_SLOTS: tuple[time, ...] = (time(13, 0), time(20, 30))
CAPTURE_TOLERANCE_MINUTES = 45


@dataclass(frozen=True)
class Route:
    """A directional city pair in the sample."""

    route_code: str
    origin: str
    destination: str
    display_name: str


#: Sample frame: top domestic city pairs by DGCA passenger volume. Directional
#: (DEL-BOM and BOM-DEL price differently and are separate items).
SAMPLE_ROUTES: tuple[Route, ...] = (
    Route("DEL-BOM", "DEL", "BOM", "Delhi – Mumbai"),
    Route("BOM-DEL", "BOM", "DEL", "Mumbai – Delhi"),
    Route("DEL-BLR", "DEL", "BLR", "Delhi – Bengaluru"),
    Route("BLR-DEL", "BLR", "DEL", "Bengaluru – Delhi"),
    Route("BOM-BLR", "BOM", "BLR", "Mumbai – Bengaluru"),
    Route("DEL-CCU", "DEL", "CCU", "Delhi – Kolkata"),
    Route("DEL-HYD", "DEL", "HYD", "Delhi – Hyderabad"),
    Route("BOM-GOI", "BOM", "GOI", "Mumbai – Goa"),
    Route("DEL-GAU", "DEL", "GAU", "Delhi – Guwahati"),
    Route("BLR-CCU", "BLR", "CCU", "Bengaluru – Kolkata"),
)


# ---------------------------------------------------------------------------
# Matched-model identity
# ---------------------------------------------------------------------------

#: The tuple that makes two observations on different days "the same item".
#: This is what makes the index matched-model rather than a moving average of
#: whatever happened to be on sale.
ITEM_KEY_FIELDS: tuple[str, ...] = ("carrier", "flight_no", "brand_family", "booking_class")

#: The elementary aggregate stratum. Prices are only ever compared inside a cell.
CELL_KEY_FIELDS: tuple[str, ...] = ("route_code", "advance_days")


def item_key(row: dict) -> str:
    """Stable matched-model identity for one observation."""
    return "|".join(str(row[f]) for f in ITEM_KEY_FIELDS)


def cell_key(row: dict) -> tuple[str, int]:
    """Elementary aggregate stratum for one observation."""
    return (str(row["route_code"]), int(row["advance_days"]))


@dataclass(frozen=True)
class BasketSpec:
    """Serialisable snapshot of the basket definition, exposed by /methodology.

    Publishing this alongside the index is the difference between a number and a
    statistic.
    """

    observation_unit: dict = field(default_factory=lambda: dict(OBSERVATION_UNIT))
    brand_family: str = TARGET_BRAND_FAMILY
    advance_windows: tuple[int, ...] = ADVANCE_WINDOWS
    routes: tuple[str, ...] = tuple(r.route_code for r in SAMPLE_ROUTES)
    index_capture_slot_ist: str = INDEX_CAPTURE_SLOT.isoformat()
    nonstop_only: bool = NONSTOP_ONLY
    exclude_codeshare: bool = EXCLUDE_CODESHARE


BASKET = BasketSpec()
