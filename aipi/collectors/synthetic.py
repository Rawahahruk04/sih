"""Calibrated synthetic fare generator.

Purpose and its limits, stated up front
--------------------------------------
Real daily collection cannot span 30+ days inside a hackathon build window. The
defensible substitute is synthetic data that is pushed through the *production*
cleaning and index code, so what is being demonstrated is the pipeline, not the
simulator.

The failure mode this module is built to avoid: **calibrating on the validation
target**. If levels are anchored to DGCA and the index is then validated against
DGCA, the exercise measures the simulator. So the generator:

  * takes an explicit `calibration_months` list and records it on the output,
  * derives *dynamics* (lead-time curve, weekday pattern, volatility, churn)
    from structural assumptions stated here in code — never from the validation
    months,
  * anchors only the *level*, and only from the declared calibration months.

`aipi.validation.backtest.assert_holdout` consumes `calibration_months` and raises
if the validation window overlaps it. The discipline is enforced, not promised.

Every generated row carries `source='synthetic'`. Nothing downstream ever mixes
synthetic and real rows without that column making it visible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

import numpy as np
import pandas as pd

from aipi.basket import ADVANCE_WINDOWS, INDEX_CAPTURE_SLOT, SAMPLE_ROUTES, Route

IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Structural assumptions. These are the model, and they are declared, not fitted.
# ---------------------------------------------------------------------------

#: Fare multiplier by days-to-departure, relative to the 14-day window. Airlines
#: price inventory buckets upward as departure approaches; this is the single most
#: important structural feature of airfare and the reason a matched-model index
#: must never compare across windows.
LEADTIME_MULTIPLIER: dict[int, float] = {
    60: 0.88,
    30: 0.92,
    21: 0.96,
    14: 1.00,
    7: 1.12,
    3: 1.34,
    1: 1.62,
}

#: Travel-day-of-week multiplier (Mon=0). Friday and Sunday carry business and
#: weekend-return demand. This is what the DOW adjustment must recover.
TRAVEL_DOW_MULTIPLIER: dict[int, float] = {
    0: 1.02,
    1: 0.95,
    2: 0.96,
    3: 1.01,
    4: 1.10,
    5: 1.00,
    6: 1.07,
}

#: Base fare in INR at the 14-day window, mid-week, before item and noise terms.
#: Order-of-magnitude figures for Indian domestic economy; replaced by
#: DGCA-anchored levels when `calibration_levels` is supplied.
ROUTE_BASE_FARE: dict[str, float] = {
    "DEL-BOM": 5200.0,
    "BOM-DEL": 5300.0,
    "DEL-BLR": 5600.0,
    "BLR-DEL": 5500.0,
    "BOM-BLR": 4400.0,
    "DEL-CCU": 5900.0,
    "DEL-HYD": 5300.0,
    "BOM-GOI": 3400.0,
    "DEL-GAU": 7800.0,
    "BLR-CCU": 6400.0,
}

#: Route-specific multiplier on the underlying fare trend. Declared, not fitted,
#: and deliberately heterogeneous — this is the assumption that decides whether
#: the weighting specification matters at all.
#:
#: If every route inflated at the same rate, any set of weights summing to one
#: would return the same headline, and the expenditure-vs-passenger distinction
#: would be arithmetically irrelevant. That is not the world: Indian route-level
#: fare inflation disperses widely, because pricing power tracks competition.
#: Thin high-fare routes (DEL-GAU, BLR-CCU) carry one or two operators and price
#: accordingly; dense trunk routes are disciplined by capacity; BOM-GOI is a
#: leisure route in monsoon off-season and deflates.
#:
#: The dispersion is positively correlated with fare LEVEL, so expenditure
#: weights (which up-weight expensive routes relative to passenger counts) give a
#: materially different headline. The sign is a modelling choice; the fact that
#: the choice of weights changes the answer is not.
ROUTE_TREND_MULTIPLIER: dict[str, float] = {
    "DEL-GAU": 2.4,
    "BLR-CCU": 1.8,
    "DEL-CCU": 1.4,
    "DEL-HYD": 1.0,
    "DEL-BLR": 0.85,
    "BLR-DEL": 0.75,
    "BOM-DEL": 0.65,
    "DEL-BOM": 0.55,
    "BOM-BLR": 0.35,
    "BOM-GOI": -0.70,
}

#: Base-period passengers per month, used to build expenditure weights in demos.
ROUTE_PASSENGERS: dict[str, float] = {
    "DEL-BOM": 420_000.0,
    "BOM-DEL": 415_000.0,
    "DEL-BLR": 360_000.0,
    "BLR-DEL": 355_000.0,
    "BOM-BLR": 290_000.0,
    "DEL-CCU": 240_000.0,
    "DEL-HYD": 230_000.0,
    "BOM-GOI": 150_000.0,
    "DEL-GAU": 95_000.0,
    "BLR-CCU": 88_000.0,
}

CARRIERS: tuple[tuple[str, str], ...] = (
    ("6E", "SAVER"),
    ("AI", "COMFORT"),
    ("QP", "ECOSAVER"),
    ("SG", "SPICESAVER"),
)

#: A seat is never certain to be gone. Caps the cheapness uplift so a deep
#: discount does not deterministically vanish from the sample.
SOLDOUT_PROB_CAP = 0.65


@dataclass
class SyntheticConfig:
    start: date
    n_days: int = 75
    routes: tuple[Route, ...] = SAMPLE_ROUTES
    windows: tuple[int, ...] = ADVANCE_WINDOWS
    seed: int = 20260826

    #: Underlying inflation in the fare level, per day, in log points. Scaled per
    #: route by ROUTE_TREND_MULTIPLIER.
    trend_pct_per_day: float = 0.06
    #: Idiosyncratic day-level shock to a whole route (fuel, competitor action).
    route_shock_sd: float = 0.012
    #: Per-observation noise.
    obs_noise_sd: float = 0.030
    #: Persistent per-flight premium (time of day, aircraft, slot quality).
    item_effect_sd: float = 0.080

    flights_per_route: int = 10
    #: Probability a given flight is absent from the schedule on a given day.
    #: This is what makes the item set churn, and therefore what makes the
    #: chained-vs-multilateral distinction bite.
    churn_prob: float = 0.06

    #: Flash-sale probability and depth (log points). Indian carriers run frequent
    #: limited-period sales, and a discount that later reverts is the textbook
    #: generator of chain drift: the down-link and the up-link do not cancel once
    #: the item set churns between them, so a chained index ratchets.
    promo_prob: float = 0.05
    promo_depth: float = 0.22

    #: Probability the cheap bucket has closed, before the lead-time and
    #: cheapness uplifts.
    soldout_base_prob: float = 0.04
    #: Elasticity of availability to relative price, in the exponent. The cheap
    #: seat is the one that goes; modelling sold-out as INDEPENDENT of price makes
    #: churn nearly harmless in aggregate and understates the case for a
    #: multilateral index. Real inventory does not behave that way.
    soldout_price_sensitivity: float = 8.0
    #: Fraction of rows where the source returns only a total, no tax breakdown.
    missing_split_frac: float = 0.35

    #: Months (YYYY-MM) whose DGCA levels were used to anchor. Consumed by
    #: `assert_holdout`.
    calibration_months: tuple[str, ...] = ()
    #: Optional DGCA-derived route level overrides, applied to the level only.
    calibration_levels: dict[str, float] = field(default_factory=dict)


RAW_COLUMNS = (
    "capture_ts",
    "capture_date",
    "travel_date",
    "advance_days",
    "origin",
    "destination",
    "carrier",
    "flight_no",
    "fare_brand",
    "booking_class",
    "cabin",
    "stops",
    "is_codeshare",
    "base_fare",
    "taxes",
    "fees",
    "total_fare",
    "currency",
    "source",
    "is_soldout",
)


def generate(config: SyntheticConfig) -> pd.DataFrame:
    """Produce raw-quote rows in the exact shape the real collector emits."""
    rng = np.random.default_rng(config.seed)

    base_levels = dict(ROUTE_BASE_FARE)
    base_levels.update(config.calibration_levels)

    # Per-route flight rosters, fixed for the whole run so item effects persist —
    # a flight's premium must be a property of the flight, not fresh noise.
    rosters: dict[str, list[dict]] = {}
    for route in config.routes:
        flights = []
        for i in range(config.flights_per_route):
            carrier, brand = CARRIERS[i % len(CARRIERS)]
            flights.append(
                {
                    "carrier": carrier,
                    "flight_no": f"{carrier}-{100 + i * 37 % 900}",
                    "fare_brand": brand,
                    "booking_class": "V" if i % 3 else "U",
                    "item_effect": float(rng.normal(0.0, config.item_effect_sd)),
                }
            )
        rosters[route.route_code] = flights

    rows: list[dict] = []
    for day_offset in range(config.n_days):
        capture_date = config.start + timedelta(days=day_offset)
        capture_ts = datetime.combine(capture_date, INDEX_CAPTURE_SLOT, tzinfo=IST)
        # Capture time jitters a little, as a real scheduled job does.
        capture_ts += timedelta(minutes=int(rng.integers(-12, 13)))

        for route in config.routes:
            route_shock = float(rng.normal(0.0, config.route_shock_sd))
            base = base_levels.get(route.route_code, 5000.0)
            trend = (
                config.trend_pct_per_day
                / 100.0
                * day_offset
                * ROUTE_TREND_MULTIPLIER.get(route.route_code, 1.0)
            )

            for advance_days in config.windows:
                travel_date = capture_date + timedelta(days=advance_days)
                lead = np.log(LEADTIME_MULTIPLIER.get(advance_days, 1.0))
                dow = np.log(TRAVEL_DOW_MULTIPLIER[travel_date.weekday()])
                cell_log = np.log(base) + lead + dow + trend + route_shock

                for flight in rosters[route.route_code]:
                    if rng.random() < config.churn_prob:
                        continue  # not in the schedule today

                    # Draw the price FIRST, then availability from it. Inventory
                    # closure is not exogenous: the cheap seat is the one that
                    # goes. Drawing sold-out independently of the fare (the easy
                    # way) makes churn almost harmless in aggregate and quietly
                    # removes the empirical case for a multilateral index.
                    noise = float(rng.normal(0.0, config.obs_noise_sd))
                    promo = -config.promo_depth if rng.random() < config.promo_prob else 0.0
                    rel = flight["item_effect"] + noise + promo

                    leadtime_uplift = 1.0 + 3.0 / (1.0 + advance_days)
                    soldout_prob = min(
                        SOLDOUT_PROB_CAP,
                        config.soldout_base_prob
                        * leadtime_uplift
                        * float(np.exp(-config.soldout_price_sensitivity * rel)),
                    )
                    is_soldout = bool(rng.random() < soldout_prob)

                    total = np.nan if is_soldout else round(float(np.exp(cell_log + rel)), 2)

                    give_split = (not is_soldout) and rng.random() > config.missing_split_frac
                    if give_split:
                        # UDF/PSF-style fixed component plus an ad-valorem part.
                        taxes = round(470.0 + 0.16 * total / 1.16, 2)
                        fees = 0.0
                        base_fare = round(total - taxes - fees, 2)
                    else:
                        taxes = np.nan
                        fees = np.nan
                        base_fare = np.nan

                    rows.append(
                        {
                            "capture_ts": capture_ts,
                            "capture_date": capture_date,
                            "travel_date": travel_date,
                            "advance_days": advance_days,
                            "origin": route.origin,
                            "destination": route.destination,
                            "carrier": flight["carrier"],
                            "flight_no": flight["flight_no"],
                            "fare_brand": flight["fare_brand"],
                            "booking_class": flight["booking_class"],
                            "cabin": "ECONOMY",
                            "stops": 0,
                            "is_codeshare": False,
                            "base_fare": base_fare,
                            "taxes": taxes,
                            "fees": fees,
                            "total_fare": total,
                            "currency": "INR",
                            "source": "synthetic",
                            "is_soldout": is_soldout,
                        }
                    )

    df = pd.DataFrame(rows, columns=list(RAW_COLUMNS))
    df.attrs["calibration_months"] = list(config.calibration_months)
    df.attrs["generator_seed"] = config.seed
    df.attrs["is_synthetic"] = True
    return df


def demo_passengers(routes: tuple[Route, ...] = SAMPLE_ROUTES) -> dict[str, float]:
    return {r.route_code: ROUTE_PASSENGERS.get(r.route_code, 100_000.0) for r in routes}


def demo_base_fares(routes: tuple[Route, ...] = SAMPLE_ROUTES) -> dict[str, float]:
    return {r.route_code: ROUTE_BASE_FARE.get(r.route_code, 5_000.0) for r in routes}


def inject_dirty_rows(df: pd.DataFrame, *, seed: int = 7, n: int = 40) -> pd.DataFrame:
    """Corrupt a sample of rows so the cleaning pipeline has real work to do.

    A cleaning report showing zero rejections proves nothing. These defects mirror
    what real collectors actually emit: currency leaks, business-cabin bleed,
    parse failures, and stale duplicate offers.
    """
    rng = np.random.default_rng(seed)
    out = df.copy()
    if out.empty:
        return out

    idx = rng.choice(out.index, size=min(n, len(out)), replace=False)
    chunk = np.array_split(idx, 5)

    out.loc[chunk[0], "currency"] = "USD"  # currency leak
    out.loc[chunk[1], "total_fare"] = 250.0  # below plausible floor
    out.loc[chunk[2], "total_fare"] = 480_000.0  # business-cabin / paise error
    out.loc[chunk[3], "flight_no"] = ""  # parse failure
    out.loc[chunk[4], "advance_days"] = -3  # arithmetic error

    # Stale duplicate offers: the same flight seen twice in one capture.
    dupes = out.loc[rng.choice(out.index, size=min(25, len(out)), replace=False)].copy()
    dupes["capture_ts"] = dupes["capture_ts"] - pd.Timedelta(minutes=3)
    dupes["total_fare"] = pd.to_numeric(dupes["total_fare"], errors="coerce") * 1.02

    return pd.concat([out, dupes], ignore_index=True)


def slot_drift_rows(df: pd.DataFrame, *, seed: int = 11, frac: float = 0.08) -> pd.DataFrame:
    """Move a fraction of captures far off the index slot.

    Exercises the capture-slot discipline: these rows must be retained as
    intraday evidence and excluded from the index.
    """
    rng = np.random.default_rng(seed)
    out = df.copy()
    if out.empty:
        return out
    n = max(1, int(len(out) * frac))
    idx = rng.choice(out.index, size=n, replace=False)
    out.loc[idx, "capture_ts"] = out.loc[idx, "capture_ts"] + pd.Timedelta(hours=9)
    return out


def default_demo_frame(
    *,
    start: date | None = None,
    n_days: int = 75,
    dirty: bool = True,
    seed: int = 20260826,
) -> pd.DataFrame:
    """One call that produces the full demo dataset, defects included."""
    cfg = SyntheticConfig(
        start=start or (date(2026, 6, 1)),
        n_days=n_days,
        seed=seed,
        calibration_months=("2026-04", "2026-05"),
    )
    df = generate(cfg)
    if dirty:
        df = inject_dirty_rows(df)
        df = slot_drift_rows(df)
        df.attrs["calibration_months"] = list(cfg.calibration_months)
    return df


def capture_slot_variants(df: pd.DataFrame, slots: tuple[time, ...]) -> pd.DataFrame:
    """Add auxiliary intraday captures — the input to the volatility chart.

    Intraday variance is the empirical case for daily collection. A single daily
    capture cannot demonstrate it, so the collector takes extra slots that are
    deliberately excluded from the index.
    """
    frames = [df]
    for i, slot in enumerate(slots):
        alt = df.copy()
        base_ts = pd.to_datetime(alt["capture_ts"])
        shift_hours = slot.hour - INDEX_CAPTURE_SLOT.hour
        shift_min = slot.minute - INDEX_CAPTURE_SLOT.minute
        alt["capture_ts"] = base_ts + pd.Timedelta(hours=shift_hours, minutes=shift_min)
        # Intraday revision: fares drift within the day, more so close to departure.
        rng = np.random.default_rng(1000 + i)
        adv = pd.to_numeric(alt["advance_days"], errors="coerce").fillna(30).to_numpy()
        scale = 0.006 + 0.030 / (1.0 + adv)
        factor = np.exp(rng.normal(0.0, scale))
        alt["total_fare"] = pd.to_numeric(alt["total_fare"], errors="coerce") * factor
        alt["base_fare"] = np.nan
        alt["taxes"] = np.nan
        frames.append(alt)
    return pd.concat(frames, ignore_index=True)
