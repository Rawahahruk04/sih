"""Duffel fare collector — real quotes, mapped onto the same contract as synthetic.

The whole point of this module is that it is *interchangeable* with
`aipi.collectors.synthetic`: it emits a DataFrame with exactly `RAW_COLUMNS`, so
cleaning, the index engine, the API and the dashboard are untouched by the switch
from simulated to real fares. Swapping the data source must not be a rewrite.

Three things here are methodological, not incidental:

  * **The raw payload is archived before it is parsed.** You cannot re-request
    yesterday's fares — a quote is a perishable observation. If the mapping code
    turns out to be wrong, the archive is the only way to rebuild the series
    without losing history, so writing it is not optional.

  * **Currency is checked, never converted.** Duffel quotes in the organisation's
    billing currency. Converting a EUR quote into INR would make the index move
    with the EUR/INR rate, which is exchange-rate movement masquerading as
    airfare inflation. A mismatch is therefore a hard error: fix the billing
    currency at the source, do not paper over it in the pipeline.

  * **`live_mode` is recorded per row.** Test-mode inventory is simulated. Mixing
    simulated and live observations in one series would be undetectable after the
    fact, so the flag travels with the data and `source` distinguishes them.

Sold-out is deliberately NOT set here. It is an inference from an item
*disappearing* between captures, which is a cross-day comparison this module
cannot make from a single snapshot; the cleaning layer owns it.
"""

from __future__ import annotations

import json
import logging
import time as _time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd

from aipi.basket import ADVANCE_WINDOWS, SAMPLE_ROUTES, Route
from aipi.collectors.errors import CollectionError
from aipi.collectors.synthetic import RAW_COLUMNS
from aipi.config import Settings, get_settings

log = logging.getLogger(__name__)

OFFER_REQUEST_PATH = "/air/offer_requests"

#: Retry on transient failures only. A 4xx that is not 429 is a bug in our
#: request and retrying it just burns quota.
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 1.5

__all__ = ["CollectionError", "DuffelClient", "DuffelConfig", "collect", "offers_to_rows"]


@dataclass
class DuffelConfig:
    token: str
    version: str = "v2"
    base_url: str = "https://api.duffel.com"
    timeout_s: float = 60.0
    cabin_class: str = "economy"
    #: 0 = non-stop only, which the basket requires (NONSTOP_ONLY).
    max_connections: int = 0
    #: Per-airline search timeout Duffel accepts (2s-60s).
    supplier_timeout_ms: int = 20_000
    #: Polite spacing between requests; the quota is generous but the courtesy is
    #: cheap and keeps us well clear of 429s.
    pause_s: float = 0.35
    archive_dir: Path | None = None
    routes: Sequence[Route] = field(default_factory=lambda: SAMPLE_ROUTES)
    advance_windows: Sequence[int] = field(default_factory=lambda: ADVANCE_WINDOWS)

    @classmethod
    def from_settings(cls, settings: Settings | None = None, **overrides) -> DuffelConfig:
        s = settings or get_settings()
        if not s.duffel_token:
            raise CollectionError(
                "AIPI_DUFFEL_TOKEN is not set. Put it in .env (gitignored); never in code."
            )
        base = {
            "token": s.duffel_token,
            "version": s.duffel_version,
            "base_url": s.duffel_base_url,
            "timeout_s": s.duffel_timeout_s,
        }
        base.update(overrides)
        return cls(**base)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


class DuffelClient:
    """Thin, retrying client for the one endpoint this collector needs."""

    def __init__(self, config: DuffelConfig, client: httpx.Client | None = None) -> None:
        self._c = config
        self._http = client or httpx.Client(timeout=config.timeout_s)
        self._owns_http = client is None

    def __enter__(self) -> DuffelClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._c.token}",
            "Duffel-Version": self._c.version,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def search(self, origin: str, destination: str, departure_date: date) -> dict:
        """One offer request. Returns the `data` object, offers embedded."""
        body = {
            "data": {
                "slices": [
                    {
                        "origin": origin,
                        "destination": destination,
                        "departure_date": departure_date.isoformat(),
                    }
                ],
                "passengers": [{"type": "adult"}],
                "cabin_class": self._c.cabin_class,
                "max_connections": self._c.max_connections,
            }
        }
        url = f"{self._c.base_url}{OFFER_REQUEST_PATH}"
        params = {
            "return_offers": "true",
            "supplier_timeout": str(self._c.supplier_timeout_ms),
        }

        last: str = "no attempt made"
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                r = self._http.post(url, headers=self._headers, params=params, json=body)
            except httpx.HTTPError as exc:  # network-level
                last = f"{type(exc).__name__}: {exc}"
            else:
                if r.status_code < 300:
                    return r.json()["data"]
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code not in RETRY_STATUS:
                    break
            if attempt < MAX_ATTEMPTS:
                sleep_s = BACKOFF_BASE_S**attempt
                log.warning(
                    "duffel search %s-%s %s failed (%s); retry %d/%d in %.1fs",
                    origin, destination, departure_date, last, attempt, MAX_ATTEMPTS, sleep_s,
                )
                _time.sleep(sleep_s)
        raise CollectionError(
            f"Duffel search failed for {origin}-{destination} {departure_date}: {last}"
        )


# ---------------------------------------------------------------------------
# Mapping: Duffel offer -> RAW_COLUMNS
# ---------------------------------------------------------------------------


def _num(value: object) -> float | None:
    """Duffel sends money as decimal strings; nulls are real (tax_amount)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def offers_to_rows(
    payload: dict,
    *,
    route: Route,
    advance_days: int,
    capture_ts: datetime,
    index_currency: str = "INR",
    strict_currency: bool = True,
) -> list[dict]:
    """Flatten one offer-request payload into RAW_COLUMNS rows.

    One row per (offer, brand) — i.e. per purchasable product on a flight number.
    Deliberately no de-duplication and no brand filtering here: the collector's
    job is to record what the airline offered, and every narrowing decision
    belongs in the cleaning layer where it is counted and published. A collector
    that quietly drops rows makes the row-accounting a lie.
    """
    offers = payload.get("offers") or []
    live_mode = bool(payload.get("live_mode", False))
    capture_date = capture_ts.astimezone(UTC).date()
    rows: list[dict] = []
    currencies: set[str] = set()

    for offer in offers:
        slices = offer.get("slices") or []
        if len(slices) != 1:
            continue  # one-way basket; a multi-slice offer is not our product
        sl = slices[0]
        segments = sl.get("segments") or []
        if len(segments) != 1:
            continue  # non-stop only; enforced again here, not merely requested
        seg = segments[0]

        marketing = seg.get("marketing_carrier") or {}
        operating = seg.get("operating_carrier") or {}
        seg_pax = (seg.get("passengers") or [{}])[0]

        currency = offer.get("total_currency")
        if currency:
            currencies.add(str(currency))

        total = _num(offer.get("total_amount"))
        base = _num(offer.get("base_amount"))
        tax = _num(offer.get("tax_amount")) or 0.0
        if total is None:
            continue
        if base is None:
            base = total - tax
        # Duffel exposes base + tax; anything left over is carrier/booking fees.
        fees = round(total - base - tax, 6)
        if abs(fees) < 0.005:
            fees = 0.0

        travel_date = seg.get("departing_at") or ""
        travel_date = str(travel_date)[:10]

        rows.append(
            {
                "capture_ts": capture_ts,
                "capture_date": capture_date,
                "travel_date": travel_date,
                "advance_days": int(advance_days),
                "origin": route.origin,
                "destination": route.destination,
                "carrier": str(marketing.get("iata_code") or ""),
                "flight_no": (
                    f"{marketing.get('iata_code', '')}-"
                    f"{seg.get('marketing_carrier_flight_number', '')}"
                ),
                # Raw brand label, NOT yet mapped to a family. BRAND_FAMILY_MAP is
                # applied in cleaning so that unmapped brands are logged and
                # dropped explicitly rather than coerced here in the dark.
                "fare_brand": str(sl.get("fare_brand_name") or ""),
                "booking_class": str(seg_pax.get("fare_basis_code") or ""),
                "cabin": str(seg_pax.get("cabin_class") or "economy").upper(),
                "stops": len(segments) - 1,
                "is_codeshare": bool(
                    operating.get("iata_code")
                    and marketing.get("iata_code")
                    and operating["iata_code"] != marketing["iata_code"]
                ),
                "base_fare": base,
                "taxes": tax,
                # Duffel exposes base + tax only; UDF and convenience charges are
                # not separately identified in its offer schema, so they are left
                # null rather than guessed. The cleaning layer's split model owns
                # imputing them, where the imputation is flagged and counted.
                "udf_fee": None,
                "convenience_fee": None,
                "fees": fees,
                "total_fare": total,
                "currency": str(currency or ""),
                "source": "duffel" if live_mode else "duffel_test",
                # Test-mode inventory is simulated, so it is NOT 'real' data for
                # index purposes even though it came off a real API.
                "data_mode": "real" if live_mode else "synthetic",
                # Sold-out is an inference from disappearance across captures, not
                # a field on an offer. Cleaning owns it; asserting it here would be
                # fabrication.
                "is_soldout": False,
            }
        )

    if strict_currency and currencies and currencies != {index_currency}:
        raise CollectionError(
            f"Fares quoted in {sorted(currencies)} but the index currency is "
            f"{index_currency}. Refusing to convert: an FX-converted quote makes the "
            "index move with the exchange rate, which is not airfare inflation. Set "
            "the Duffel billing currency to "
            f"{index_currency}, or run with strict_currency=False for a pipeline "
            "smoke test whose output must NOT be published."
        )
    return rows


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def _archive(payload: dict, directory: Path, route: Route, advance_days: int, ts: datetime) -> None:
    """Persist the raw payload. A quote is perishable; the archive is the record."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = ts.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{stamp}_{route.route_code}_{advance_days:02d}d.json"
    path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def collect(
    config: DuffelConfig | None = None,
    *,
    capture_ts: datetime | None = None,
    client: DuffelClient | None = None,
    index_currency: str | None = None,
    strict_currency: bool = True,
    routes: Iterable[Route] | None = None,
    advance_windows: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Collect one capture slot across the basket. Emits exactly RAW_COLUMNS.

    Partial failure is fatal by design (see `CollectionError`): a capture missing
    routes is worse than no capture, because the index cannot distinguish absent
    supply from cheap supply.
    """
    settings = get_settings()
    config = config or DuffelConfig.from_settings(settings)
    index_currency = index_currency or settings.index_currency
    capture_ts = capture_ts or datetime.now(UTC)
    route_list = list(routes if routes is not None else config.routes)
    windows = list(advance_windows if advance_windows is not None else config.advance_windows)

    owns_client = client is None
    client = client or DuffelClient(config)
    rows: list[dict] = []
    try:
        for route in route_list:
            for adv in windows:
                departure = capture_ts.date() + timedelta(days=int(adv))
                payload = client.search(route.origin, route.destination, departure)
                if config.archive_dir is not None:
                    _archive(payload, config.archive_dir, route, int(adv), capture_ts)
                got = offers_to_rows(
                    payload,
                    route=route,
                    advance_days=int(adv),
                    capture_ts=capture_ts,
                    index_currency=index_currency,
                    strict_currency=strict_currency,
                )
                log.info(
                    "collected %s %sd dep=%s offers=%d rows=%d",
                    route.route_code, adv, departure, len(payload.get("offers") or []), len(got),
                )
                rows.extend(got)
                if config.pause_s:
                    _time.sleep(config.pause_s)
    finally:
        if owns_client:
            client.close()

    if not rows:
        raise CollectionError(
            "Collection returned zero rows. Publishing an empty capture would look "
            "like a fare collapse; failing loudly is the only safe behaviour."
        )
    return pd.DataFrame(rows, columns=list(RAW_COLUMNS))
