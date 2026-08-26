"""Playwright scraping base: one strategy, reused by every site.

Why network-response interception, not CSS-selector scraping
--------------------------------------------------------------
Airline and OTA search pages are single-page apps: the page shell loads, then
JavaScript calls the site's own internal search API and renders the results
client-side. Two ways to get the data out:

  1. Wait for render, then parse the DOM with CSS selectors.
  2. Let the page load normally, but listen for the network response the page
     itself makes to its internal API, and parse that JSON directly.

(2) is what this module does, via `capture_search_payload()`. CSS-selector
scraping breaks on every visual redesign (weekly, for a consumer travel site);
the internal API response shape is far more stable because it is the site's
own data contract with its own frontend, not decoration. This is standard
practice for scraping JS-rendered SPAs, and it is also **gentler** on the
target: one intercepted response per search, not repeated DOM polling.

What this module does NOT do
-----------------------------
It does not defeat CAPTCHAs, spoof TLS fingerprints, or rotate through
residential proxy pools to evade detection. A `CaptchaEncountered` or
`RobotsDisallowed` stops the run and surfaces the event; ethical-scraping
compliance (robots.txt, rate limiting, a truthful User-Agent) is a hard gate,
not a suggestion — see `aipi.collectors.scraper.robots`.

Per-site setup this module cannot do for you
-----------------------------------------------
Every subclass must declare `RESULT_URL_SUBSTRING`: the fragment of the
internal search-API URL to listen for (e.g. `"/api/search/air"`). That
fragment is specific to each site's frontend build and changes when the site
redeploys; discovering/re-verifying it is a five-minute manual step (open the
network tab, run a search, find the request carrying fare data) documented in
`docs/SCRAPER_SETUP.md`. No amount of code can discover it without first
loading the live page in a real browser, which this module does — the one
site-specific fact a human still has to supply is that URL fragment.
"""

from __future__ import annotations

import json
import logging
import random
import time as _time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from aipi.collectors.errors import CaptchaEncountered, CollectionError
from aipi.collectors.scraper.robots import DEFAULT_USER_AGENT, RobotsGate

log = logging.getLogger(__name__)

#: Substrings found in a challenge page's own markup/response. Detection only —
#: never an attempt to solve or route around them.
CAPTCHA_MARKERS: tuple[str, ...] = (
    "captcha",
    "are you a robot",
    "unusual traffic",
    "access denied",
    "please verify you are a human",
    "px-captcha",
    "cf-challenge",
)


@dataclass
class ScraperConfig:
    headless: bool = True
    nav_timeout_ms: int = 45_000
    result_wait_ms: int = 20_000
    #: Floor spacing between requests to one origin; robots.txt Crawl-delay
    #: overrides this upward if the publisher declares a longer one.
    min_delay_s: float = 3.0
    max_delay_s: float = 6.0
    user_agent: str = DEFAULT_USER_AGENT
    archive_dir: Path | None = None
    max_attempts: int = 2


class BaseSiteScraper(ABC):
    """One instance per source (one airline site or one OTA).

    Subclasses implement `search_url()` (the page to open for one
    origin/destination/date) and `parse(payload)` (site JSON -> RAW_COLUMNS
    rows). Everything else — robots gate, rate limiting, CAPTCHA detection,
    retries, raw-payload archiving — is shared here so it is enforced
    identically for every source, not re-implemented (and possibly forgotten)
    per site.
    """

    #: Human-readable key used as `source` in RAW_COLUMNS, e.g. "indigo_site".
    SOURCE_NAME: str = "unset"
    #: e.g. "https://www.goindigo.in" — used for the robots.txt origin check.
    BASE_URL: str = "unset"
    #: Fragment of the internal search-API URL to intercept. See module
    #: docstring: this is the one fact that must be verified against the live
    #: site and kept current.
    RESULT_URL_SUBSTRING: str = "unset"
    #: True for an OTA aggregating multiple carriers, False for a single-airline
    #: direct site. Carrier is then read from the payload rather than assumed.
    IS_AGGREGATOR: bool = False

    def __init__(
        self, config: ScraperConfig | None = None, robots: RobotsGate | None = None
    ) -> None:
        self.config = config or ScraperConfig()
        self.robots = robots or RobotsGate(user_agent=self.config.user_agent)

    # -- to implement per site ------------------------------------------------

    @abstractmethod
    def search_url(self, origin: str, destination: str, departure: date) -> str:
        """The page URL that, once loaded, triggers the internal search call."""

    @abstractmethod
    def parse(
        self, payload: dict[str, Any], *, origin: str, destination: str, departure: date
    ) -> list[dict]:
        """Map one intercepted JSON payload to RAW_COLUMNS-shaped dict rows."""

    # -- shared mechanics -------------------------------------------------------

    def _polite_sleep(self, url: str) -> None:
        floor = self.robots.crawl_delay_s(url, self.config.min_delay_s)
        _time.sleep(max(floor, random.uniform(self.config.min_delay_s, self.config.max_delay_s)))

    def _detect_captcha(self, text: str) -> None:
        low = text.lower()
        if any(marker in low for marker in CAPTCHA_MARKERS):
            raise CaptchaEncountered(
                f"{self.SOURCE_NAME}: challenge page detected mid-capture. Stopping "
                "this source for the run rather than attempting to solve it."
            )

    def _archive(
        self, payload: Any, *, origin: str, destination: str, departure: date, ts: datetime
    ) -> None:
        if self.config.archive_dir is None:
            return
        self.config.archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = ts.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        path = (
            self.config.archive_dir
            / f"{stamp}_{self.SOURCE_NAME}_{origin}{destination}_{departure.isoformat()}.json"
        )
        path.write_text(json.dumps(payload, separators=(",", ":"), default=str), encoding="utf-8")

    def capture_search_payload(
        self, page: Any, origin: str, destination: str, departure: date
    ) -> dict[str, Any]:
        """Navigate, wait for the internal search API response, return its JSON.

        `page` is a Playwright `Page`. Kept as a loose type so this module can be
        imported (and unit tested) without Playwright installed — only code paths
        that actually drive a browser need the dependency at runtime.
        """
        url = self.search_url(origin, destination, departure)
        self.robots.check(url)

        captured: dict[str, Any] = {}

        def _on_response(response: Any) -> None:
            if self.RESULT_URL_SUBSTRING in response.url and response.request.method in (
                "GET",
                "POST",
            ):
                try:
                    captured["payload"] = response.json()
                    captured["url"] = response.url
                except Exception:  # noqa: BLE001 - not every matching response is JSON
                    pass

        page.on("response", _on_response)
        try:
            page.goto(url, timeout=self.config.nav_timeout_ms, wait_until="domcontentloaded")
            page.wait_for_timeout(self.config.result_wait_ms)
            self._detect_captcha(page.content())
        finally:
            page.remove_listener("response", _on_response)

        if "payload" not in captured:
            raise CollectionError(
                f"{self.SOURCE_NAME}: no response matching '{self.RESULT_URL_SUBSTRING}' was "
                "observed. Either the search did not return results, or the site's internal "
                "API endpoint has changed and RESULT_URL_SUBSTRING needs updating — see "
                "docs/SCRAPER_SETUP.md."
            )
        return captured["payload"]

    def collect_one(
        self, page: Any, origin: str, destination: str, departure: date
    ) -> list[dict]:
        """One origin/destination/date search, with retry and archiving."""
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                ts = datetime.now(UTC)
                payload = self.capture_search_payload(page, origin, destination, departure)
                self._archive(
                    payload, origin=origin, destination=destination, departure=departure, ts=ts
                )
                rows = self.parse(
                    payload, origin=origin, destination=destination, departure=departure
                )
                self._polite_sleep(self.search_url(origin, destination, departure))
                return rows
            except CaptchaEncountered:
                raise  # never retry past a detected challenge
            except CollectionError as exc:
                last_exc = exc
                if attempt < self.config.max_attempts:
                    log.warning(
                        "%s %s-%s %s attempt %d/%d failed: %s",
                        self.SOURCE_NAME, origin, destination, departure, attempt,
                        self.config.max_attempts, exc,
                    )
                    _time.sleep(2.0 * attempt)
        raise last_exc or CollectionError(
            f"{self.SOURCE_NAME}: collection failed with no exception recorded"
        )
