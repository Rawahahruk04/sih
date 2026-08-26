# Scraper setup — the manual step this code cannot do for you

`aipi/collectors/scraper/` gives you a working Playwright harness (robots.txt
gate, rate limiting, CAPTCHA detection, retries, raw-payload archiving) and one
class per source named in PS 26056: IndiGo, Air India, Air India Express,
Akasa Air, SpiceJet, MakeMyTrip, Yatra, EaseMyTrip, Cleartrip, Ixigo, Goibibo.

What it does **not** ship with is a verified `RESULT_URL_SUBSTRING` (the
fragment of each site's internal search-API URL) or a hand-tuned `parse()` for
each site's real JSON shape — those can only be discovered by loading the live
page in a real browser, and they were written as documented placeholders, not
guessed and shipped as if verified. This is normal, ongoing scraper
maintenance, not a gap specific to this project: every scraper of a JS-driven
site needs this same five-minute step redone whenever the target redeploys
its frontend.

## Per-site calibration (~5 minutes each)

1. Open the site's flight-search page in Chrome/Firefox with DevTools open on
   the **Network** tab, filtered to `Fetch/XHR`.
2. Run one real one-way economy search (e.g. DEL → BOM, a date ~2 weeks out).
3. Find the request that returns the fare list — usually the largest JSON
   response, often named something like `search`, `fareList`, `results`.
4. Copy a distinctive substring of its URL path into that site's
   `RESULT_URL_SUBSTRING` in `aipi/collectors/scraper/sites/{airlines,otas}.py`.
5. Save the response body (DevTools → right-click → "Save response") and run
   it through `aipi.collectors.scraper.heuristics.generic_parse` in a REPL. If
   it raises `CollectionError` naming the keys it saw, either:
   - add the site's field names to `FIELD_ALIASES` in `heuristics.py` (if the
     shape is close to the common pattern), or
   - override `parse()` in that site's class with an exact mapping (if it
     isn't — most OTAs will need this).
6. Re-run `python -m scripts.run_scrape --headed` for that source only and
   confirm real rows come out the other end.

Do this for the airline sites first — five sites, lower legal ambiguity, and
they are `enabled=True` by default in `aipi/collectors/scraper/registry.py`.

## Before enabling any OTA

OTAs are `enabled=False` by default in the registry. `RobotsGate` enforces
`robots.txt` automatically at runtime and will refuse a disallowed path on its
own — but a Terms-of-Use prohibition on automated access is a separate,
site-specific legal question `robots.txt` does not encode, and this codebase
cannot answer it for you. Read the ToU of each OTA you intend to enable before
flipping its `enabled` flag, and keep a record of that review (e.g. a short
note in `docs/COLLECTION_RISK.md`) alongside the decision.

## Running it

```bash
pip install -e ".[scrape]"
playwright install chromium

python -m scripts.run_scrape                 # airline sites, headless
python -m scripts.run_scrape --headed         # watch it run, for calibration
python -m scripts.run_scrape --with-otas      # + any OTA you've reviewed and enabled
```

Each run writes `data/raw/<timestamp>_scraped.parquet` (never overwritten —
every capture is a new file) and archives every raw JSON response under
`data/scraper_archive/<timestamp>/`, so a mapping bug can be fixed and the
run re-parsed from the archive without re-hitting the live site.

## Scheduling the daily capture

Add a GitHub Actions workflow at `.github/workflows/daily-capture.yml` that
runs `python -m scripts.run_scrape` at the index capture slot
(`AIPI_CAPTURE_SLOT_IST`, see `aipi/basket.py`) in IST, `actions/upload-artifact`
on `data/raw/` and `data/scraper_archive/`, and installs
`playwright install --with-deps chromium` in the job before running. Because
GitHub Actions `cron` is a queue, not a guaranteed-time scheduler (see the
README), the pipeline already checks the actual `capture_ts` against
`AIPI_CAPTURE_TOLERANCE_MIN` and records the drift rather than assuming the
job ran on time — a late run becomes visible, not silently mixed into the
index.

## Feeding scraped data into the pipeline

`scripts/run_pipeline.py` currently reads from the synthetic generator. Point
it at `data/raw/*.parquet` (concatenated) instead of `default_demo_frame()`
once you have real captures — the cleaning pipeline and index engine take any
DataFrame shaped like `RAW_COLUMNS`, synthetic or scraped, identically.
