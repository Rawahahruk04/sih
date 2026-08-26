"""Test probe for live site scrapers.

Allows testing one specific scraper against one route and one departure date,
logging intercepted network responses, URL matching, and extracted fare rows.

Usage:
    python scripts/test_live_scraper.py --source indigo
    python scripts/test_live_scraper.py --source air_india
    python scripts/test_live_scraper.py --source akasa
    python scripts/test_live_scraper.py --source spicejet
    python scripts/test_live_scraper.py --source makemytrip
"""
import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright
from aipi.collectors.scraper.base import ScraperConfig
from aipi.collectors.scraper.registry import all_scrapers
from aipi.collectors.scraper.robots import RobotsGate
from aipi.collectors.errors import CaptchaEncountered, CollectionError, RobotsDisallowed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("test_scraper")

def main():
    parser = argparse.ArgumentParser(description="Test a single scraper on a single route")
    parser.add_argument("--source", type=str, default="indigo", help="indigo | air_india | air_india_express | akasa | spicejet | makemytrip | yatra | easemytrip | cleartrip | ixigo | goibibo")
    parser.add_argument("--origin", type=str, default="DEL", help="Origin IATA (default: DEL)")
    parser.add_argument("--dest", type=str, default="BOM", help="Destination IATA (default: BOM)")
    parser.add_argument("--days", type=int, default=14, help="Advance purchase days (default: 14)")
    parser.add_argument("--headed", action="store_true", help="Show visible browser window")
    args = parser.parse_args()

    scrapers = all_scrapers()
    target_cls = None
    for s in scrapers:
        if args.source.lower() in s.SOURCE_NAME.lower():
            target_cls = s
            break

    if not target_cls:
        print(f"Error: Unknown source '{args.source}'. Available sources:")
        for s in scrapers:
            print(f"  - {s.SOURCE_NAME}")
        return 1

    departure = date.today() + timedelta(days=args.days)
    log.info("Testing scraper '%s' on %s -> %s for departure %s", target_cls.SOURCE_NAME, args.origin, args.dest, departure)
    
    archive_dir = Path("data/scraper_test_archive")
    archive_dir.mkdir(parents=True, exist_ok=True)
    config = ScraperConfig(
        headless=not args.headed,
        archive_dir=archive_dir,
        nav_timeout_ms=45000,
        result_wait_ms=15000,
        min_delay_s=2.0,
        max_delay_s=4.0
    )
    robots = RobotsGate(user_agent=config.user_agent)
    scraper = target_cls(config=config, robots=robots)

    url = scraper.search_url(args.origin, args.dest, departure)
    log.info("Target Search URL: %s", url)

    # 1. Test Robots.txt check
    try:
        log.info("Checking robots.txt at %s...", scraper.BASE_URL)
        robots.check(url)
        delay = robots.crawl_delay_s(url, config.min_delay_s)
        log.info("✅ robots.txt check passed! Allowed crawl delay: %.1fs", delay)
    except RobotsDisallowed as exc:
        log.warning("❌ robots.txt disallows this URL: %s", exc)
        return 1
    except Exception as exc:
        log.warning("⚠️ robots.txt fetch note: %s", exc)

    # 2. Launch browser and attempt capture
    log.info("Launching Playwright Chromium...")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless)
        context = browser.new_context(user_agent=config.user_agent)
        page = context.new_page()

        # Log network requests to show what the live SPA is doing
        intercepted_urls = []
        def on_response(response):
            if any(ext in response.url for ext in ["/api", "/search", "/flight", "/booking", "json"]):
                intercepted_urls.append((response.status, response.url[:90]))
        page.on("response", on_response)

        try:
            log.info("Navigating to %s (waiting for network responses)...", url)
            try:
                page.goto(url, timeout=config.nav_timeout_ms, wait_until="domcontentloaded")
            except Exception as e:
                log.warning("Page navigation notice: %s", e)

            log.info("Page loaded. Waiting %.1fs for SPA search results to render...", config.result_wait_ms / 1000.0)
            page.wait_for_timeout(config.result_wait_ms)

            # Check page title and content
            title = page.title()
            log.info("Page title: '%s'", title)
            
            # Print top intercepted APIs
            log.info("Observed %d API/data responses during session:", len(intercepted_urls))
            for status, u in intercepted_urls[:8]:
                log.info("  [%s] %s...", status, u)

            # Check for CAPTCHA markers
            content = page.content()
            for marker in ["captcha", "are you a robot", "unusual traffic", "px-captcha", "cf-challenge"]:
                if marker in content.lower():
                    log.warning("⚠️ Anti-bot challenge marker '%s' detected in page content.", marker)

            # Attempt extraction via scraper
            log.info("Testing payload extraction with RESULT_URL_SUBSTRING='%s'...", scraper.RESULT_URL_SUBSTRING)
            try:
                rows = scraper.collect_one(page, args.origin, args.dest, departure)
                log.info("✅ SUCCESS! Extracted %d fare rows:", len(rows))
                for i, r in enumerate(rows[:5], 1):
                    log.info("  Row #%d: Carrier=%s Flight=%s Fare=INR %.2f (Base=%.2f, Tax=%.2f)",
                             i, r.get("carrier"), r.get("flight_no"), r.get("total_fare"),
                             r.get("base_fare") or 0.0, r.get("taxes") or 0.0)
            except CollectionError as e:
                log.info("Scraper extraction status: %s", e)
                log.info("Tip: Inspect the intercepted API URLs above to update RESULT_URL_SUBSTRING in %s if the site has updated its internal API path.", target_cls.__module__)

        except Exception as exc:
            log.error("Live test encountered error: %s", exc)
        finally:
            context.close()
            browser.close()

    return 0

if __name__ == "__main__":
    sys.exit(main())
