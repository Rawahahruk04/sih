# Collection risk register

Every data source this project can use has a way of looking like it is
working while quietly producing nothing publishable. This file is the honest
record of what has actually been checked, and what each source's failure mode
looks like.

## API sources

**Amadeus Self-Service (`test` environment).** Serves largely **cached** data.
An index built on it is flat and worthless, and the failure is silent — the
API returns 200s the whole time. Run the fare-drift smoke test (48h go/no-go)
before trusting it, and rely on `construct_validity_checks()`'s
`suspiciously_flat` alarm as the automated form of the same check.

**Duffel (`duffel_test_` token).** Verified 2026-08-26 on DEL-BOM: schema and
fare-brand fields are real, but inventory is **simulated** — offers come back
from Duffel Airways (ZZ), British Airways and American Airlines, not any
Indian domestic carrier, and quoted in EUR. `live_mode` on the response is the
only trustworthy indicator; never infer it from the token prefix. A live
token is required before this source can feed a publishable series.

## Direct scraping sources — live smoke test, 2026-08-26

`python -m scripts.run_scrape --headed` was actually run against live sites
(DEL→BOM, one route) as a smoke test of the scraper harness itself, not as a
production capture. Results, because they are evidence about what this
project can rely on, not just what the code intends:

| Source | Outcome | What it means |
|---|---|---|
| IndiGo (`goindigo.in`) | `RobotsGate` **refused** the booking search path — disallowed by the site's own `robots.txt` | This source is not usable at that URL under the ethical-scraping constraint this project holds itself to. Either find a robots.txt-permitted entry point (e.g. a public fare-calendar page, if one exists and is allowed) or drop IndiGo from direct scraping and rely on an API aggregator for that carrier's fares. |
| Air India (`airindia.com`) | robots.txt fetch **timed out**; `RobotsGate` fails closed (treats as fully disallowed) | Inconclusive, not a refusal — a flaky network read, a WAF slowing anonymous requests, or a genuinely slow robots.txt endpoint. Re-test before concluding either way; the safe default (fail closed) is doing its job. |
| Air India Express (`airindiaexpress.com`) | A **CAPTCHA/anti-bot challenge page** was served and correctly detected (`CaptchaEncountered`), not bypassed | This source needs either a different access pattern (an API partner integration) or is out of scope for direct scraping under the "detect, don't defeat" policy this project holds. |
| Akasa Air (`akasaair.com`) | Page loaded, but no network response matched the placeholder `RESULT_URL_SUBSTRING` | Expected — that value is an unverified placeholder pending the calibration step in `docs/SCRAPER_SETUP.md`, not a site refusal. |
| SpiceJet | Not reached before the smoke test was stopped (still queued) | Untested. |

**The headline finding**: the ethical-scraping gate is not decorative — it
already refused one of the five named airline sites (IndiGo) on its first
real run, and correctly stopped on a CAPTCHA from a second (Air India
Express) rather than working around it. For a submission to a statistical
agency, "our scraper respects the constraint even when that costs us a
source" is a stronger claim than "our scraper gets every source," and it is
backed by this actual run, not asserted.

**Practical implication for the basket.** If IndiGo and Air India Express
cannot be reached under this policy, the realistic near-term data-collection
mix is: 2-3 direct airline sites confirmed reachable (SpiceJet, Akasa once
calibrated, Air India once the timeout is resolved) plus an OTA (once its ToS
is reviewed and its endpoint calibrated) plus an API aggregator (Duffel, once
on a live token) as backfill for carriers direct scraping cannot reach. That
mixed-source design should be stated explicitly in the submission rather than
implied — it is the honest shape of what "ethical, compliant scraping" of
these specific eleven sites actually yields.

## OTA sources

Not yet reviewed for Terms-of-Use compliance and therefore `enabled=False` by
default in `aipi/collectors/scraper/registry.py`. See
`docs/SCRAPER_SETUP.md` → "Before enabling any OTA" for the required review
before switching any of them on.
