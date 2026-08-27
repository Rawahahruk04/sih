# Live demo runbook

Scope: `aipi/demo_config.py` — **2 routes** (DEL-BOM, DEL-BLR) x **2 windows**
(T+7, T+30). This is deliberately smaller than the production basket (12
routes x 5 windows). See that module's docstring for why: fewer requests means
fewer chances for one slow site to stall the room.

**Read this before walking on stage.** As of the last check (2026-08-27), zero
of the four candidate sources returned clean data — see the results table
below. Re-run the check yourself; site and API availability change day to day.

---

## Before the presentation (do this the night before, and again 1 hour before)

### 1. Check which source is actually usable right now

```bash
python -m scripts.check_demo_sources
```

Latest result on this repo:

| source | usable | why |
|---|---|---|
| `duffel` | no | `AIPI_DUFFEL_TOKEN` not set — **fixable**: sign up for a free Duffel test token at duffel.com and put it in `.env` |
| `akasa_site` | no | page navigation timed out (site itself, not network — real internet was confirmed working) |
| `spicejet_site` | no | endpoint not yet calibrated (`RESULT_URL_SUBSTRING` is a placeholder — see `docs/SCRAPER_SETUP.md`) |
| `air_india_site` | no | `robots.txt` disallows the booking path — **do not override this**, it is correct |

**Recommendation: get a Duffel token before the demo.** It is a real API, not a
scrape, so it removes CAPTCHA/robots.txt/timeout risk entirely from at least
one source and is the most reliable thing you can put on stage. IndiGo
(robots.txt-blocked) and Air India Express (CAPTCHA) are excluded on principle
and are not going to change — do not attempt them live.

### 2. Start from the seeded baseline (already built)

```bash
docker compose up
# or, from source:
python -m scripts.seed_synthetic --days 45
uvicorn aipi.api.main:app --reload
```

Confirm it is 100% synthetic before you start:

```bash
curl -s localhost:8000/health | python -m json.tool
```

Expect `data_mode.synthetic_share: 1.0`, `is_demo_data: true`. This is your
"before" screenshot.

### 3. Rehearse the live run once, off stage

```bash
python -m scripts.run_live_demo --source duffel
# or, if a scraper passed step 1:
python -m scripts.run_live_demo --source scrape --scraper spicejet_site
```

Time it. If it is close to 60 seconds, cut it further before showtime (fewer
routes/windows in `aipi/demo_config.py` — but that changes the shared demo
scope, so agree that with whoever else is presenting from it).

**A realistic expectation to set with yourself, not the audience**: 2 routes x
2 windows is 4 rows against a ~23,000-row synthetic baseline. `real_share`
moves from `0.0` to roughly `0.0002` (0.02%) — genuinely measurable and
verifiable in the JSON, but not a dramatic bar-chart jump on screen. **Narrate
the number rather than relying on a visual**: "we just added 4 real quotes;
watch real_share go from 0.000000 to 0.000175 in the response." If you want a
more dramatic visual instead, reseed a smaller baseline just before stage:
`python -m scripts.seed_synthetic --days 3` produces a baseline small enough
that 4 real rows move the percentage by a visible amount — but do this as a
deliberate choice, and say so, rather than let a small baseline read as if it
were the production system's normal size.

---

## During the presentation

### Step A — show the "before" state

```bash
curl -s localhost:8000/health | python -m json.tool
```

Point at `data_mode.synthetic_share: 1.0` and the banner text. Say plainly:
*"Right now this is 100% simulated data — that's the honest starting point."*

### Step B — run the live collection, on screen

```bash
python -m scripts.run_live_demo --source duffel
```

This is the "watch it happen" beat. Rows print as they land:

```
  [2026-08-27T10:15:02+00:00] 6E   DEL-BOM T+7   INR     5436  source=duffel  data_mode=real
  ...
collected 4 row(s) in 6.3s
```

It also prints a BEFORE/AFTER `data_mode` comparison and writes
`data/live_demo/blended_raw.parquet`.

### Step C — restart the API to serve the blend

```bash
docker compose restart api
# or, from source: Ctrl-C the uvicorn process, run it again
```

This is deliberate, not a limitation to apologize for: the API is a read
service with no write endpoint (by design — see the API-hardening notes), and
"restart to pick up new data" is a normal, explainable step for a batch-style
statistical pipeline. Say so if asked.

### Step D — show the "after" state

```bash
curl -s localhost:8000/health | python -m json.tool
```

`data_mode.synthetic_share` has moved. Narrate the exact number (see the
realistic-expectation note above).

### Step E — the demo-scope heatmap

```bash
curl -s "localhost:8000/api/v1/index/routes/heatmap" | python -m json.tool
```

Point out `DEL-BOM` and `DEL-BLR` specifically — the two routes the live run
just touched.

### Step F — the real government-data comparison

```bash
curl -s localhost:8000/api/v1/validation/dgca | python -m json.tool
```

Show `secondary_reference` — `is_placeholder: false`, `source:
"mospi_cpi_transport"`, 152 months of real MoSPI CPI Transport & Communication
data. **Say the caveat out loud, don't let the audience infer it themselves**:
*"This reference is real government data. The fares being indexed are still
mostly synthetic — those are two different facts, and the report states both."*
This endpoint is completely unchanged for the demo; it already had this wired
in from the earlier CPI-reference work.

---

## If live collection fails on stage

It will print a clear failure and exit non-zero — it does **not** silently
fall back to fabricated data:

```
FAILED after 9.7s: spicejet_site: no response matching '/api/v1/search/flight-search' was observed...
This is the documented fallback trigger — see docs/LIVE_DEMO_RUNBOOK.md ...
```

**Say this out loud, verbatim in spirit, and move on:**

> "The live source didn't respond — that happens with real external
> dependencies. Here's the 45-day seeded baseline we validated ahead of time."

Then continue with Steps E and F against the baseline that was already running
before Step B — nothing about it changed, since a failed run inserts zero rows
and never touches `blended_raw.parquet`. This is a legitimate demo outcome, not
a failure to hide: it is the same "detect and stop, never fake it" discipline
the scraper harness applies to robots.txt and CAPTCHAs, applied to the demo
itself.

**Do not**, under any circumstance:
- retry against a source `check_demo_sources.py` marked unusable, hoping it
  works this time on stage
- manually insert a hand-typed "real" row to force the banner to move
- claim the fallback baseline is live data

---

## Appendix: inspecting the live data directly

```bash
python -c "
import sqlite3
c = sqlite3.connect('data/live_demo/live_demo.db')
for row in c.execute('select capture_ts, carrier, origin, destination, total_fare, source from raw_quotes_live order by inserted_at desc limit 10'):
    print(row)
"
```

Every row inserted by `run_live_demo.py` is committed individually and
durably — this query works while a collection is still in progress, from a
second terminal, which is itself a nice "no really, it's landing right now"
moment if you want it.
