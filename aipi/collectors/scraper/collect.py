"""Orchestrate one capture slot across every enabled site scraper.

Mirrors `aipi.collectors.duffel.collect()`'s contract and discipline
deliberately: same RAW_COLUMNS output, same "partial failure inside a source
is logged, a source that errors on every route is dropped for the run and
reported, a run producing zero total rows is fatal." A statistical pipeline
must never publish a capture that looks complete but silently missed a whole
source.

Playwright is imported lazily inside `collect()`, not at module load, so the
rest of the codebase (cleaning, index, API, tests) never needs it installed —
only an actual scrape run does.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from aipi.basket import ADVANCE_WINDOWS, SAMPLE_ROUTES, Route
from aipi.collectors.errors import CaptchaEncountered, CollectionError, RobotsDisallowed
from aipi.collectors.scraper.base import BaseSiteScraper, ScraperConfig
from aipi.collectors.scraper.registry import enabled_scrapers
from aipi.collectors.scraper.robots import RobotsGate
from aipi.collectors.synthetic import RAW_COLUMNS

log = logging.getLogger(__name__)


def collect(
    *,
    scrapers: Sequence[type[BaseSiteScraper]] | None = None,
    routes: Iterable[Route] | None = None,
    advance_windows: Iterable[int] | None = None,
    include_otas: bool = False,
    config: ScraperConfig | None = None,
    capture_ts: datetime | None = None,
) -> pd.DataFrame:
    """Run every enabled scraper across the basket. Emits exactly RAW_COLUMNS.

    A source raising `RobotsDisallowed` or failing every route it attempts is
    dropped from this run (logged loudly) rather than aborting the whole
    capture — one broken source must not take down the other ten. A source
    hitting `CaptchaEncountered` is dropped the same way: the challenge is
    reported, never worked around.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise CollectionError(
            "playwright is not installed. Install the 'scrape' extra: "
            "pip install -e '.[scrape]' && playwright install chromium"
        ) from exc

    config = config or ScraperConfig()
    capture_ts = capture_ts or datetime.now(UTC)
    route_list = list(routes if routes is not None else SAMPLE_ROUTES)
    windows = list(advance_windows if advance_windows is not None else ADVANCE_WINDOWS)
    scraper_classes = (
        list(scrapers) if scrapers is not None else enabled_scrapers(include_otas=include_otas)
    )

    robots = RobotsGate(user_agent=config.user_agent)
    rows: list[dict] = []
    source_errors: dict[str, list[str]] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless)
        try:
            for cls in scraper_classes:
                scraper = cls(config=config, robots=robots)
                source_rows = 0
                context = browser.new_context(user_agent=config.user_agent)
                page = context.new_page()
                try:
                    for route in route_list:
                        for adv in windows:
                            departure = capture_ts.date() + timedelta(days=int(adv))
                            try:
                                got = scraper.collect_one(
                                    page, route.origin, route.destination, departure
                                )
                                rows.extend(got)
                                source_rows += len(got)
                            except CaptchaEncountered as exc:
                                log.error(
                                    "%s: %s — dropping source for this run",
                                    scraper.SOURCE_NAME, exc,
                                )
                                source_errors.setdefault(scraper.SOURCE_NAME, []).append(str(exc))
                                raise  # stop this source entirely, do not keep probing it
                            except RobotsDisallowed as exc:
                                log.error(
                                    "%s: %s — dropping source for this run",
                                    scraper.SOURCE_NAME, exc,
                                )
                                source_errors.setdefault(scraper.SOURCE_NAME, []).append(str(exc))
                                raise
                            except CollectionError as exc:
                                log.warning(
                                    "%s %s-%s %s: %s", scraper.SOURCE_NAME, route.origin,
                                    route.destination, departure, exc,
                                )
                                source_errors.setdefault(scraper.SOURCE_NAME, []).append(str(exc))
                except (CaptchaEncountered, RobotsDisallowed):
                    continue
                finally:
                    context.close()
                log.info(
                    "%s: %d rows from %d route/window cells",
                    scraper.SOURCE_NAME, source_rows, len(route_list) * len(windows),
                )
        finally:
            browser.close()

    if not rows:
        raise CollectionError(
            "Scraper collection returned zero rows across all sources. Publishing an "
            "empty capture would look like a fare collapse; failing loudly is the only "
            f"safe behaviour. Per-source errors: {source_errors}"
        )

    df = pd.DataFrame(rows, columns=list(RAW_COLUMNS))
    df.attrs["source_errors"] = source_errors
    df.attrs["is_synthetic"] = False
    return df


def archive_dir_for(base: Path, run_date: date) -> Path:
    return base / run_date.isoformat()
