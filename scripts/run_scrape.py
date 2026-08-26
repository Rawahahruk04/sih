"""One scheduled capture: scrape every enabled source, archive raw payloads,
append to the running raw-quote store.

    python -m scripts.run_scrape                  # airline sites only (default)
    python -m scripts.run_scrape --with-otas       # + OTAs (verify ToS first)
    python -m scripts.run_scrape --headed          # watch the browser, for debugging

This is the daily job GitHub Actions cron should invoke (see
docs/SCRAPER_SETUP.md for the workflow). It never overwrites prior captures:
each run appends a dated parquet file under data/raw/, so a bad run is
visible and discardable rather than silently merged into the series.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from aipi.collectors.errors import CollectionError
from aipi.collectors.scraper.base import ScraperConfig
from aipi.collectors.scraper.collect import collect

RAW_DIR = Path("data/raw")
ARCHIVE_DIR = Path("data/scraper_archive")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="Run one scraper capture across enabled sources")
    ap.add_argument(
        "--with-otas", action="store_true", help="include OTA sources (verify ToS first)"
    )
    ap.add_argument("--headed", action="store_true", help="run a visible browser (debugging)")
    ap.add_argument("--out", type=str, default=str(RAW_DIR))
    ap.add_argument("--archive", type=str, default=str(ARCHIVE_DIR))
    args = ap.parse_args()

    capture_ts = datetime.now(UTC)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = Path(args.archive) / capture_ts.strftime("%Y%m%dT%H%M%SZ")

    config = ScraperConfig(headless=not args.headed, archive_dir=archive_dir)

    try:
        df = collect(include_otas=args.with_otas, config=config, capture_ts=capture_ts)
    except CollectionError as exc:
        logging.error("capture failed: %s", exc)
        return 1

    stamp = capture_ts.strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"{stamp}_scraped.parquet"
    df.to_parquet(out_path, index=False)
    errors = df.attrs.get("source_errors", {})
    logging.info(
        "wrote %d rows to %s (raw payloads archived under %s)", len(df), out_path, archive_dir
    )
    if errors:
        logging.warning("per-source errors this run: %s", errors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
