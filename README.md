# AIPI — Real-Time Airfare Price Index for India

Smart India Hackathon 2026 · Problem Statement **26056** · Ministry of Statistics and
Programme Implementation (MoSPI)

A daily, methodologically defensible price index for Indian domestic airfares, built to
the standard a statistical agency would actually apply to a candidate CPI component.

> This is a **methodology proof of concept**, not an official government statistic.

---

## The problem worth solving

MoSPI currently captures airfares at a low frequency. Airfares are among the most
volatile prices in the consumption basket, so the question is not "can we collect more
data" — it is **how much measurement error does sparse sampling actually introduce**.

This repo answers that from data, not assertion. From `scripts/run_pipeline.py`:

```
Sampling 1 day per month from the same fares misses the true monthly average by
1.57% on average (3.60% at the 95th percentile), and reports the WRONG DIRECTION
of month-on-month change 27.1% of the time.

days/month     MAE %   p95 |err| %   wrong direction
         1     1.649         3.684          27.8%
         3     0.849         2.078          11.6%
         7     0.523         1.258           2.6%
        15     0.286         0.703           0.0%
```

Reaching ±1% MAE requires **3 collection days per month** under this design. That is the
policy-facing result: a concrete sampling requirement, derived by simulating the current
monthly process against a known daily truth.

---

## Five methodological decisions that carry the project

Each is implemented, tested, and quantified — not claimed.

### 1. Laspeyres weights are base-period *expenditure* shares, not passenger shares

`p₀q₀ / Σp₀q₀`, not `q₀ / Σq₀`. Using passenger counts alone silently assumes every
route has the same fare. The distinction is not cosmetic:
[`tests/test_aggregate.py`](tests/test_aggregate.py) constructs a case where it costs
**25 index points**, and the live pipeline reports the gap on real weights every run
(currently 0.319 points, **4.5% of the measured movement**).

→ [`aipi/index/aggregate.py`](aipi/index/aggregate.py) · `expenditure_weights()`

### 2. Jevons on price *relatives*, never a geometric mean of price *levels*

These coincide only when the item set is identical across periods — which airline
schedules guarantee it is not. A GM of levels reports schedule churn as inflation.
[`tests/test_elementary.py`](tests/test_elementary.py) contains
`test_gm_of_levels_records_inflation_that_nobody_paid`: two flights, **neither changes
price**, the cheap one stops operating — matched index 100.0, GM-of-levels **> 141**.

The wrong estimator is kept in the codebase (`naive_gm_level_index`) specifically so the
bias can be *measured* and published. Currently **1.19%**.

→ [`aipi/index/elementary.py`](aipi/index/elementary.py)

### 3. Chain drift is removed structurally, with GEKS — not hoped away

A daily chained index over a churning item set does not return to its starting value when
prices do. This is chain drift, and at daily frequency it is large.

The fix is a multilateral index: **GEKS-Jevons** on a rolling 25-day window with a
movement splice, so published values are never revised.
[`tests/test_geks.py`](tests/test_geks.py) is the load-bearing test file — a
hand-derived four-period panel where prices return exactly to base:

| | chained Jevons | GEKS-Jevons |
|---|---|---|
| index at `d3` (prices back to base) | **70.7107** | **100.0** |

verified to `abs=1e-9`, alongside transitivity over all triples, exact reproduction of
uniform inflation, scale invariance, and no-revision-under-splice.

In the live pipeline GEKS removes **1.86%** of drift at series end (max 2.55%).

→ [`aipi/index/geks.py`](aipi/index/geks.py)

### 4. Base period is a period *average*, not a single day

A base of `100` anchored to one arbitrary date bakes that date's noise into every
subsequent value. The base is the **geometric mean over 14 days**, and every cell is
rebased onto the *common* base window **before** upper-level aggregation. That ordering is
load-bearing: cells enter the sample on different dates, so aggregating self-normalised
cell indices would average numbers expressed on different bases — a silent, plausible-
looking error no test of the individual formulas would catch.

→ [`aipi/index/engine.py`](aipi/index/engine.py)

### 5. The observation unit is defined, so "the same item" means something

A price index requires a matched item. `OBSERVATION_UNIT` pins all of it: 1 adult,
one-way, non-stop, economy, **lowest fare within a single brand family**, total payable
inclusive of taxes, INR, excluding codeshare duplicates and ancillaries. Fare **brand**
(Saver vs Flexi) is a quality dimension, not a synonym for cabin — mixing them measures
product substitution and calls it inflation.

→ [`aipi/basket.py`](aipi/basket.py)

---

## Two ways this project could have been dishonest, and what prevents it

**Correlation on n=2.** Thirty days of collection yields one or two monthly changes.
A Pearson *r* on two points is not weak evidence, it is undefined — and "r = 0.7" from it
is the fastest way to lose a statistics judge. `backtest.py` **refuses** to emit a
correlation below n=8 and explains why. The comparison with real power pools route-months
(`route_panel_backtest`), and notes that route-months are not independent within a month.

**Calibrating on the validation target.** Anchoring synthetic back-fill to DGCA and then
validating against DGCA measures the simulator. `assert_holdout()` **raises** — not warns
— if calibration and validation months overlap. The discipline is enforced, not promised.

---

## Collection risk, stated before it bites

The Amadeus Self-Service **test** environment serves largely **cached** data. An index
built on it is flat and worthless, and the failure is silent. Two mitigations:

- a **fare-drift smoke test** as a 48-hour go/no-go before trusting the source
- `construct_validity_checks()` computes `suspiciously_flat` on every run — the automated
  form of the same check

GitHub Actions `cron` is also **not a scheduler**: it queues, delays, and disables itself
after 60 days of repo inactivity. The capture slot is fixed in IST and the *actual*
`capture_ts` is recorded and enforced with a tolerance, so a late run is visible rather
than silently mixed into the index.

---

## Running it

### One command (recommended — this is the frontend handoff)

```bash
docker compose up
```

Gives you a populated API with **no internet dependency**:

| | |
|---|---|
| Swagger | http://localhost:8000/docs |
| Dashboard | http://localhost:8000/dashboard |
| Health + lineage | http://localhost:8000/health |

### From source

```bash
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/ -q
```

```bash
# the full offline demo, with diagnostics printed
python -m scripts.run_pipeline --days 75

# 45 days of labelled synthetic data + a reference series, for the API
python -m scripts.seed_synthetic --days 45

# the real orchestration entrypoint (collect -> clean -> index -> validate)
python -m aipi.pipeline run --source parquet
python -m aipi.pipeline run --source synthetic --allow-placeholder-weights

# regenerate openapi.json for frontend codegen
python -m scripts.export_openapi
```

The pipeline is fully offline and **deterministic given `--seed`** — every printed number
is exactly reproducible, which is a requirement for anything presented as a statistic.

Note that `aipi.pipeline` **refuses to run** on placeholder weights unless you pass
`--allow-placeholder-weights`. The shipped
`data/reference/dgca_route_traffic_PLACEHOLDER.json` is illustrative, not DGCA data, and
the flag exists so nobody produces a "statistic" from it by accident.

## The API

Base path `/api/v1`. Every index response carries `data_mode` (real vs synthetic counts)
so a dashboard can render an honest demo-data banner rather than silently mixing lineages.

| Endpoint | For |
|---|---|
| `/index?freq=daily\|weekly\|monthly&from=&to=` | headline trend, all three PS-mandated frequencies |
| `/index/routes/heatmap?from=&to=` | route × date matrix, pre-shaped for a heatmap (`null` for absent cells, never 0) |
| `/index/leadtime/curve` | lead-time elasticity curve, T+15 = 100 |
| `/validation/dgca` | back-test vs the reference, with `data_mode_breakdown` and a caveat |
| `/routes` | route metadata for dropdowns |
| `/health` | latest date, series age, lineage summary |
| `/methodology` | basket, formulae, fingerprint, full cleaning row-accounting |

---

## Layout

```
aipi/
  basket.py                     observation unit, sample routes, capture slots
  config.py                     settings via AIPI_* env vars
  index/
    elementary.py               Jevons; GM-of-levels retained to measure its bias
    geks.py                     GEKS-Jevons, rolling window, movement splice
    aggregate.py                expenditure weights, Laspeyres, coverage, rebasing
    dow.py                      day-of-week decomposition
    engine.py                   orchestration; the rebase-before-aggregate ordering
  cleaning/
    contract.py                 13 validation rules with per-row reason codes
    outliers.py                 log-space median/MAD; flagged, never deleted
    decomposition.py            tax split fitted from data, never imputed onto total_fare
    pipeline.py                 11 stages with full row accounting
  validation/
    measurement_error.py        the sparse-sampling simulation above
    backtest.py                 DGCA comparison with holdout enforcement
  collectors/
    synthetic.py                declared structural assumptions, holdout-aware
tests/                          78 tests
scripts/run_pipeline.py         end-to-end offline demo
```

### On cleaning: why the rejection *reason* is kept

Validation answers "did this DataFrame pass?". A statistical pipeline needs to know
**which rows were rejected, by which rule, and why** — because an unexplained drop in
accepted observations is indistinguishable from a fall in fares. Every rejected row
carries its reason code, and `CleaningReport` accounts for every input row.

Outliers are **flagged, never deleted**, and detected in log space with median/MAD rather
than IQR on levels — IQR trims the expensive tail asymmetrically, which suppresses exactly
the signal an airfare index exists to measure.

Sold-out inventory is **not** quarantined as a missing price. The absence of a price is
information. And dropping a temporarily-unavailable item from a Jevons link is
arithmetically identical to class-mean imputation, so it needs no explicit imputation —
what it actually breaks is transitivity, which GEKS fixes structurally.

---

## Status

Built and passing: index engine, GEKS, aggregation, DOW adjustment, cleaning pipeline,
measurement-error simulation, back-test framework, FastAPI service (`/api/v1/index`,
`/index/routes`, `/index/leadtime`, `/methodology`, `/index/volatility`) with `n_obs` and
`coverage_pct` on every published value, dashboard, SQLAlchemy schema with vintage/revision
semantics, synthetic collector, Duffel API collector, and a Playwright-based scraping
harness (`aipi/collectors/scraper/`) covering all eleven sources named in PS 26056 — five
airline sites and six OTAs — with a robots.txt gate, CAPTCHA detection, rate limiting and
raw-payload archiving shared across every source.

**Honest state of the scraper**, from an actual smoke test against live sites (see
[`docs/COLLECTION_RISK.md`](docs/COLLECTION_RISK.md)): the harness works and its ethical
gates are real — it already refused IndiGo's booking path because that site's own
`robots.txt` disallows it, and it correctly detected and stopped on a CAPTCHA from Air India
Express rather than pushing through. Each site's internal search-API URL and JSON shape
still needs the one-time manual calibration step in
[`docs/SCRAPER_SETUP.md`](docs/SCRAPER_SETUP.md) before it produces real rows; OTAs are
disabled by default pending a Terms-of-Use review per source.

Also built: all three PS-mandated frequencies (weekly/monthly chained from daily, never
averaged from levels), the four-way fare decomposition with UDF and convenience charges
separately identified, queryable `real`/`synthetic` lineage end to end, heatmap and
DGCA-validation endpoints, route metadata, a seed generator producing 45 days of labelled
data with **no internet dependency**, the `aipi.pipeline` orchestration CLI, Docker
Compose, and `openapi.json` export.

**Not yet built**: Alembic migrations (the SQLAlchemy schema is defined and constrained,
not yet migrated), the `SqlStore` backend behind the `IndexStore` protocol (the API runs
on the in-memory `SnapshotStore`), a wired scheduled-capture workflow
(`.github/workflows/`), and — the critical-path item — a 30-day backtest against **real**
collected fares. That last one only becomes possible once scheduled scraping has run for
30 days, so starting collection is the bottleneck, not the code.

**Read [`docs/VALIDATION.md`](docs/VALIDATION.md) before quoting any number from this
repo.** Everything currently reported is synthetic-on-synthetic and says so.
