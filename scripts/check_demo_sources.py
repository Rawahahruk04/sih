"""Quick live reliability check for candidate live-demo sources.

Run this before committing to a source for `run_live_demo.py`, and again right
before walking on stage — a site that worked yesterday can be robots.txt-
blocked or CAPTCHA-gated today, and the whole point of a demo mode is picking
sources by evidence, not by hope.

Checks exactly one route x one window per source, with short timeouts, so this
finishes in well under a minute and does not hammer any site.

    python -m scripts.check_demo_sources
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

from aipi.collectors.errors import CaptchaEncountered, CollectionError, RobotsDisallowed
from aipi.collectors.scraper.base import ScraperConfig
from aipi.collectors.scraper.robots import RobotsGate
from aipi.collectors.scraper.sites.airlines import (
    AirIndiaSiteScraper,
    AkasaAirSiteScraper,
    SpiceJetSiteScraper,
)

logging.basicConfig(level=logging.WARNING)

CHECK_ORIGIN = "DEL"
CHECK_DEST = "BOM"
CHECK_WINDOW_DAYS = 7

CANDIDATES = (AkasaAirSiteScraper, SpiceJetSiteScraper, AirIndiaSiteScraper)


def check_duffel() -> tuple[str, bool, str]:
    from aipi.collectors.duffel import CollectionError as DuffelError
    from aipi.collectors.duffel import DuffelConfig

    try:
        DuffelConfig.from_settings()
    except DuffelError as exc:
        return ("duffel", False, str(exc))
    return ("duffel", True, "token configured (not test-called here to save quota)")


def check_scraper(cls) -> tuple[str, bool, str]:
    config = ScraperConfig(headless=True, nav_timeout_ms=20_000, result_wait_ms=8_000, max_attempts=1)
    robots = RobotsGate(user_agent=config.user_agent)
    scraper = cls(config=config, robots=robots)
    departure = date.today() + timedelta(days=CHECK_WINDOW_DAYS)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return (scraper.SOURCE_NAME, False, "playwright not installed")

    t0 = time.monotonic()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless)
            try:
                page = browser.new_context(user_agent=config.user_agent).new_page()
                rows = scraper.collect_one(page, CHECK_ORIGIN, CHECK_DEST, departure)
                dt = time.monotonic() - t0
                return (scraper.SOURCE_NAME, True, f"{len(rows)} row(s) in {dt:.1f}s")
            finally:
                browser.close()
    except RobotsDisallowed as exc:
        return (scraper.SOURCE_NAME, False, f"BLOCKED by robots.txt: {exc}")
    except CaptchaEncountered as exc:
        return (scraper.SOURCE_NAME, False, f"CAPTCHA: {exc}")
    except CollectionError as exc:
        return (scraper.SOURCE_NAME, False, f"no data (endpoint needs calibration?): {exc}")
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic script
        return (scraper.SOURCE_NAME, False, f"unexpected error: {type(exc).__name__}: {exc}")


def main() -> int:
    print(f"Checking sources against {CHECK_ORIGIN}-{CHECK_DEST}, T+{CHECK_WINDOW_DAYS}d\n")

    results = [check_duffel()]
    for cls in CANDIDATES:
        results.append(check_scraper(cls))

    print(f"{'source':<20}{'usable':<10}detail")
    print("-" * 70)
    for name, ok, detail in results:
        print(f"{name:<20}{'YES' if ok else 'no':<10}{detail}")

    usable = [name for name, ok, _ in results if ok]
    print(f"\nusable right now: {usable or 'NONE'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
