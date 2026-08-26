# Data dictionary

Units are INR per passenger unless stated. Every fare figure is **per adult,
one-way, non-stop, economy, lowest fare within the brand family, inclusive of
taxes and statutory fees** — see `aipi/basket.py::OBSERVATION_UNIT`.

## The four money components

PS 26056 requires base fare separated from "taxes, user development fee and
convenience charges". These are four distinct fields, never collapsed:

| Column | Nature | How it is imputed when missing |
|---|---|---|
| `base_fare` | The carrier's fare | **Residual**: `total − taxes − udf − convenience − fees`, so the components always reconcile to the observed total |
| `taxes` | **Ad-valorem** (GST-like); scales with the fare | Fitted `taxes = a + b·total` on rows that have a real breakdown (`taxfit-v1`), reported with its R² |
| `udf_fee` | **Fixed** per-departure charge set by the airport operator | Looked up from a per-origin schedule (`UDF_SCHEDULE`), **never regressed** — an ad-valorem imputation would make a constant fee appear to inflate with the fare |
| `convenience_fee` | OTA commercial charge; airlines do not levy it | Filled only for sources in `OTA_SOURCES`. On an airline-direct source a null is a **true zero**, not an imputation |
| `fees` | Residual bucket (carrier/booking fees that are none of the above) | Defaults to 0 |
| `total_fare` | The observed quantity and the index input | **Never imputed or modified** |

A DB `CheckConstraint` enforces the sum to within 1 INR. `split_is_imputed`
flags any row where any component was filled; `udf_schedule_version` records
which UDF schedule was used.

> The shipped `UDF_SCHEDULE` is a **placeholder** pending AERA-notified tariff
> orders per airport. Replace it and bump `UDF_SCHEDULE_VERSION`.

## Lineage and quality flags

| Column | Meaning |
|---|---|
| `data_mode` | `'real'` or `'synthetic'`. **Required** — the contract rule `BAD_DATA_MODE` fails closed if absent, and the DB has a matching CHECK. Aggregated into `/health` and every index response so a dashboard can show a demo-data banner. Duffel *test-mode* rows are `synthetic` despite coming from a real API, because the inventory is simulated |
| `source` | Which collector produced the row (`indigo_site`, `duffel`, `synthetic`, …) |
| `is_soldout` | Seen in the schedule with no bookable fare. **Excluded from the index, never valued at zero and never treated as the cheapest fare.** The absence of a price is information |
| `is_outlier` / `outlier_flag` | Beyond `k` robust sigmas from the cell's log median. **Flagged, never deleted** — deletion would break the audit trail from `raw_quotes` |
| `outlier_z` | The robust z-score behind that flag |
| `in_index_slot` | Captured within tolerance of the daily index slot. Off-slot rows are retained as intraday-volatility evidence and excluded from the index |
| `split_is_imputed` | Any money component was filled rather than observed |
| `item_key` | `carrier\|flight_no\|brand_family\|booking_class` — the matched-model identity that makes "the same item on two days" meaningful |
| `route_code` | `ORIGIN-DESTINATION`. **Directional**: DEL-BOM and BOM-DEL price differently and are separate items |
| `advance_days` | Days to departure. Must equal `travel_date − capture_date` (rule `ADVANCE_DAYS_MISMATCH`) |

## Published index values

| Column | Meaning |
|---|---|
| `series` | `headline`, `headline_dow_adjusted`, `route:DEL-BOM`, `leadtime:7`, … |
| `freq` | `daily` \| `weekly` \| `monthly`. Weekly/monthly are **derived from daily by chaining**, not computed separately |
| `value` | Index level; base period = 100 |
| `n_obs` | Index-eligible observations behind the point |
| `matched_n` | Matched pairs entering the elementary aggregate — the *effective* sample size, and the number a statistician will ask for |
| `coverage_pct` | Share of expected sample present. A headline from 6 of 12 routes is a different statistic from one from all 12 |
| `real_data_share` | Fraction of contributing observations that were real |
| `revision` / `is_current` | Vintages. Republishing a point **inserts** at `revision+1` and flips `is_current`; prior vintages are retained. Values are never overwritten |
| `n_days` / `expected_days` / `is_complete` | Weekly/monthly only. A 14-day month is flagged incomplete — plotted unlabelled beside a 31-day month it is not comparable |

## Windows and the basket

`ADVANCE_WINDOWS = (1, 7, 15, 30, 45)` — the five PS-mandated advance-purchase
windows. `WINDOW_CONFIG` also carries T+60/T+90 marked `is_extended=True`; those
are collected for a smoother curve and are **never** part of the compliance
claim. `REFERENCE_WINDOW = 15` anchors the lead-time price curve at 100.

An index is only ever computed **within** a window, never across — the windows
are the elementary strata.

`TARGET_BRAND_FAMILY = "SAVER"`. Comparing a Saver on day *t* to a Flexi on day
*t+1* is an unadjusted quality change, not a price movement. Unrecognised brands
are dropped and logged, never coerced into the target family.

## Cleaning rejection reasons

Every quarantined row carries all the reason codes it failed, not just the first:
`MISSING_TOTAL_FARE`, `FARE_BELOW_FLOOR` (<₹500), `FARE_ABOVE_CEILING`
(>₹100,000), `BAD_CURRENCY`, `NEGATIVE_ADVANCE_DAYS`, `ADVANCE_DAYS_MISMATCH`,
`TRAVEL_BEFORE_CAPTURE`, `BAD_AIRPORT_CODE`, `SAME_ORIGIN_DESTINATION`,
`MISSING_FLIGHT_NO`, `MISSING_CARRIER`, `TAX_EXCEEDS_TOTAL`,
`COMPONENTS_DO_NOT_SUM`, `BAD_DATA_MODE`.

Basket exclusions are counted **separately** from quarantine, because they are
scope decisions rather than data-quality problems: `NOT_NONSTOP`, `CODESHARE`,
`NOT_ECONOMY`, `UNRECOGNISED_BRAND`, `OUT_OF_BRAND_FAMILY`.

An unexplained fall in accepted rows is indistinguishable from a fall in fares,
which is why the full row accounting is part of the published output
(`/api/v1/methodology` → `cleaning`) rather than a debug log.
