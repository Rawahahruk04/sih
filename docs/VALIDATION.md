# Validation methodology, and the specification choices behind it

## Two different claims. Do not merge them.

This project now compares its index against **two** references, and they have
very different standing. Quoting either without the other is misleading.

| | Route/fare-level back-test (primary) | CPI Transport comparison (secondary) |
|---|---|---|
| Reference | DGCA route average fares | **MoSPI CPI Transport & Communication**, 2012=100 |
| Reference is real? | **No** — synthetic stand-in | **Yes** — genuine published government data, 152 months, Jan 2013 – Nov 2025 |
| Fares being indexed | **Synthetic** | **Synthetic** |
| Therefore the result is | Synthetic-on-synthetic: it demonstrates the pipeline, nothing more | A real reference compared against **simulated fares** — still not evidence about real airfares |
| Estimand match | Close (route-level average fares vs a route-level fare index) | **Loose** — see below |

**The claim that is true right now:** the validation *machinery* works end to
end, and one of its two references is real data correctly ingested.

**The claim that is NOT true right now:** that the index has been shown to track
real Indian airfares. Nothing here supports that yet, because every fare in the
system is simulated.

`secondary_reference.is_placeholder = false` and
`data_mode_breakdown = {"real": 0.0, "synthetic": 1.0}` are both published on
every `/api/v1/validation/dgca` response, deliberately, along with a
`SCOPE OF THE 'REAL' LABEL` note. A real reference does not launder synthetic
fares into a real result.

## The CPI Transport comparison: what it can and cannot show

**There is currently zero temporal overlap.** The MoSPI series ends
**2025-11**; the index covers **2026**. `overlap_months` reads `0`,
`n_paired_movements` reads `0`, and `pearson_r` is `null` — not because the code
failed, but because there are no paired observations and inventing them would be
fabrication. This resolves when either collection reaches a month MoSPI has
published, or the reference file is refreshed.

**The estimands differ substantially.** MoSPI's "Transport and Communication"
sub-group covers petrol, diesel, bus fares, rail fares and telephone charges as
well as air travel. Airfare is a *small component*. Even a perfect airfare index
should not track this series closely. It is a **directional sanity check against
real published data**, not a like-for-like validation — and it is labelled that
way in the response's own `notes`.

**Base periods differ** (CPI 2012=100; AIPI's base is its own collection
window), so only month-on-month *movements* are ever compared, never levels.

## Gaps in the CPI series are data, not defects

The reference is not a complete monthly grid. Three months are absent:

- **2020-04, 2020-05** — COVID lockdown suspended field price collection.
- **2019-04** — also absent in the source.

These are retained as gaps and **never interpolated or zero-filled**. A zero
would plot as a total price collapse; an interpolated value would fabricate an
observation MoSPI never made, in precisely the months when underlying prices
moved most violently. `pct_change` correctly declines to bridge a gap, so March
2020 is never compared to June 2020 as though it were one month's movement.

Malformed rows are skipped with a recorded reason rather than failing the whole
load — the same quarantine-reason discipline the cleaning pipeline uses.

## Why the synthetic backtest deliberately does not score well

## Why the synthetic backtest deliberately does not score well

The seeded reference (`scripts/seed_synthetic.py::build_dgca_reference`) is
built with its own measurement noise and a partly independent trend
(`DGCA_INDEPENDENT_TREND_SHARE = 0.30`), not derived cleanly from the same
generator as the fares.

That is intentional. Deriving both from one set of anchors would produce r ≈ 1.0
— a number that looks like a triumphant validation and proves only that two
outputs of the same function agree. A backtest that cannot fail is not a
backtest. The observed r on seeded data is moderate, which is the correct
result for two noisy instruments measuring a shared underlying signal.

## Two statistical failures the code structurally refuses

**Correlation on n=2.** 30–60 days of collection yields one or two monthly
changes. `backtest.py` refuses to emit a Pearson r below `MIN_N_FOR_CORRELATION
= 8` and explains why, rather than reporting a number that is an artefact of two
points and a straight line. The route-month panel (`route_panel_backtest`) is
the primary comparison because it pools across routes and has genuine degrees of
freedom — while noting that route-months are not independent within a month.

**Calibrating on the validation target.** `assert_holdout()` raises — not warns
— if calibration and validation months overlap.

## Specification conflicts: what was requested vs what is implemented

A build directive proposed four changes that would have replaced the index's
existing methodology. Each was declined in favour of the stronger construction,
with the requested variant retained as a **published comparison series** so the
choice is visible and measurable rather than asserted. This follows the pattern
already in the codebase, which ships `naive_gm_level_index` and
`flag_outliers_iqr` purely to quantify what the wrong choice would have cost.

| Requested | Implemented | Why, and what it costs |
|---|---|---|
| Elementary aggregate = geometric mean of fare **levels** in the cell | **Jevons on price relatives** of matched items | GM-of-levels equals Jevons only when the item set is identical across periods, which airline schedules guarantee it is not. `test_gm_of_levels_records_inflation_that_nobody_paid`: two flights, neither changes price, the cheap one stops operating → matched index 100.0, GM-of-levels **>141**. The wrong estimator is retained and its bias published as `composition_bias_pct`. |
| No multilateral index; Laspeyres + Törnqvist only | **GEKS-Jevons**, rolling window, movement splice — plus Törnqvist | Törnqvist is an *upper-level* formula; it does not address elementary-level chain drift. A daily chained index over a churning item set does not return to base when prices do. `tests/test_geks.py` pins it: prices return exactly to base, chained Jevons reads **70.71**, GEKS reads **100.0** (abs=1e-9). |
| Outliers: 1st/99th percentile winsorization | **log-space median/MAD, flagged not deleted**, cells with n<8 untrimmed | Fares are right-skewed and multiplicative. Symmetric percentile trimming on levels cuts the expensive tail harder, suppressing exactly the spike the index exists to measure. Flagging (not deleting) preserves the audit trail from `raw_quotes`. `sensitivity_report()` publishes both rules' flag counts side by side. |
| Sold-out: carry_forward / neighbour_window imputation | **Excluded from the Jevons link, never valued** | Dropping a temporarily-missing item from a Jevons link is *arithmetically identical* to class-mean imputation — the CPI Manual's prescribed treatment. Carry-forward manufactures stability and is what statistical agencies moved away from. What sold-out inventory actually breaks is transitivity, which GEKS fixes structurally. |

**Törnqvist honesty note.** The superlative cross-check is computed on
base-period weights only, because no current-period route expenditure is
observed. It therefore coincides with Laspeyres *by construction*, and
`IndexResult.notes` says so — an unexplained zero gap would otherwise read as a
validation that had passed. It becomes informative once route-level passenger
data is refreshed per period.

## Where the DGCA dependency actually sits

`tests/test_dgca_isolation.py` asserts that nothing in `aipi/index` or
`aipi/cleaning` reads the DGCA table in executable code. Prose explaining weight
provenance is deliberately permitted, because the two uses are not equivalent:

- DGCA **passenger volumes** → base-period quantity → a fixed weight. Ordinary
  CPI practice; a fixed scalar cannot transmit the target's later movements.
- DGCA **fare series** → the index's prices. This would be circular, and is what
  the isolation tests forbid.

One residual dependency is stated rather than hidden: `expenditure_weights`
accepts a `base_avg_fare` that may be DGCA-sourced. It is a base-period level
held fixed, so it does not carry month-to-month movement into the index — but it
is a dependency, and the backtest should keep reporting which months it drew on.

## Construct validity — available from day one

External validation is under-powered on a short window, so the index is also
checked against behaviour it must exhibit regardless of any reference:

- **Lead-time monotonicity**: fares must fall as booking moves earlier.
- **Flat-index alarm** (`suspiciously_flat`): a daily fare index that never moves
  means the collector is serving cached data.
- **Daily volatility** and max daily move, published as levels a reader can judge.

A statistic that fails an obvious behavioural check is wrong regardless of what
it correlates with.

## Note on the lead-time curve and the mandated windows

The PS-mandated windows (T+1, T+7, T+15, T+30, T+45) are each **one weekday
apart** from their neighbour (15−7=8, 30−15=15, 45−30=15 — all ≡1 mod 7). Since
`travel_date = capture_date + window`, window and travel weekday are confounded
on any single capture date, and the weekday effect (~15% between a Tuesday and a
Friday departure) is large enough to invert a ~6% lead-time gap.

The published curve therefore pools **exactly 7 consecutive captures**
(`CURVE_POOL_DAYS`), so each window spans all seven travel weekdays once and the
effect cancels exactly rather than being modelled away. This was found by the
monotonicity test failing when the windows changed — it is a real property of
the mandated window set, not a tuning parameter.
