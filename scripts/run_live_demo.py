"""Live demo mode: small, fast, watchable collection for a stage presentation.

    python -m scripts.run_live_demo --source duffel
    python -m scripts.run_live_demo --source scrape --scraper spicejet_site

Scope is `aipi.demo_config` (2 routes x 2 windows), NOT the production basket —
see that module's docstring. This finishes in well under a minute against a
working source, prints every row as it lands, and appends to a durable SQLite
file so "watch real data land in storage" is literally true and inspectable
with a plain `sqlite3 data/live_demo/live_demo.db` while it runs.

One correction to a natural assumption: rows do NOT get `data_mode='real'`
unconditionally. The Duffel collector already distinguishes a live token from a
test token (`live_mode` on the response) and labels test-mode rows `synthetic`,
because a test-mode quote is simulated inventory regardless of arriving over a
real HTTP call. Overriding that to force `'real'` would make the demo's own
lineage field lie — which defeats the entire point of having one. Scraped rows
from a real airline site ARE unconditionally `'real'`, since there is no
test/live distinction to make there.

After collection, the live batch is combined with the existing 45-day synthetic
baseline (never discarded — that is the demo beat: watch the blend shift) and
run through the unmodified cleaning + index pipeline. The result is written to
`data/live_demo/blended_raw.parquet`; restart the API (or `docker compose
restart api`) to have it boot from the blend — see
docs/LIVE_DEMO_RUNBOOK.md for the exact sequence.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd

from aipi.cleaning import clean
from aipi.collectors.errors import CollectionError
from aipi.collectors.synthetic import RAW_COLUMNS, default_demo_frame
from aipi.demo_config import DEMO_ROUTES, DEMO_WINDOWS
from aipi.index.engine import compute_index
from aipi.weights import load_weights

LIVE_DEMO_DIR = Path("data/live_demo")
DB_PATH = LIVE_DEMO_DIR / "live_demo.db"
BLENDED_PATH = LIVE_DEMO_DIR / "blended_raw.parquet"

log = logging.getLogger("run_live_demo")


# ---------------------------------------------------------------------------
# durable, inspectable storage
# ---------------------------------------------------------------------------


def _ensure_db(conn: sqlite3.Connection) -> None:
    cols_sql = ", ".join(f'"{c}" TEXT' for c in RAW_COLUMNS)
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS raw_quotes_live ({cols_sql}, run_id TEXT, inserted_at TEXT)"
    )
    conn.commit()


def _insert_row(conn: sqlite3.Connection, row: dict, run_id: str) -> None:
    cols = [*RAW_COLUMNS, "run_id", "inserted_at"]
    values = [str(row.get(c, "")) for c in RAW_COLUMNS] + [
        run_id,
        datetime.now(UTC).isoformat(),
    ]
    placeholders = ",".join("?" for _ in cols)
    conn.execute(
        f'INSERT INTO raw_quotes_live ({",".join(cols)}) VALUES ({placeholders})', values
    )
    # Committed per row, not batched: the row must be durable and visible to
    # anything reading the file (e.g. `sqlite3 ... "select count(*) ..."` on a
    # second terminal) the instant it lands, which is the whole demo beat.
    conn.commit()


def _print_row(row: dict) -> None:
    fare = row.get("total_fare")
    fare_str = f"{fare:>8.0f}" if isinstance(fare, (int, float)) else f"{'—':>8}"
    print(
        f"  [{row['capture_ts']}] {str(row['carrier']):<4} "
        f"{row['origin']}-{row['destination']} T+{row['advance_days']:<3} "
        f"INR {fare_str}  source={row['source']:<14} data_mode={row['data_mode']}"
    )


# ---------------------------------------------------------------------------
# collection, one source implementation each
# ---------------------------------------------------------------------------


def collect_duffel_cell(route, window: int, capture_ts: datetime) -> list[dict]:
    from aipi.collectors.duffel import DuffelClient, DuffelConfig, offers_to_rows

    config = DuffelConfig.from_settings()
    departure = capture_ts.date() + timedelta(days=window)
    with DuffelClient(config) as client:
        payload = client.search(route.origin, route.destination, departure)
    return offers_to_rows(payload, route=route, advance_days=window, capture_ts=capture_ts)


def collect_scrape_cells(scraper_name: str) -> list[tuple]:
    """Returns [(route, window, rows)] for every DEMO_ROUTES x DEMO_WINDOWS cell.

    One Playwright browser is shared across cells — launching per cell would
    both be slower and needlessly noisy against the target site.
    """
    from aipi.collectors.scraper.base import ScraperConfig
    from aipi.collectors.scraper.registry import all_scrapers
    from aipi.collectors.scraper.robots import RobotsGate

    cls = next((c for c in all_scrapers() if c.SOURCE_NAME == scraper_name), None)
    if cls is None:
        names = [c.SOURCE_NAME for c in all_scrapers()]
        raise CollectionError(f"unknown scraper {scraper_name!r}. Known: {names}")

    from playwright.sync_api import sync_playwright

    config = ScraperConfig(headless=True, nav_timeout_ms=20_000, result_wait_ms=8_000, max_attempts=1)
    robots = RobotsGate(user_agent=config.user_agent)
    scraper = cls(config=config, robots=robots)

    out: list[tuple] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless)
        try:
            page = browser.new_context(user_agent=config.user_agent).new_page()
            for route in DEMO_ROUTES:
                for window in DEMO_WINDOWS:
                    departure = date.today() + timedelta(days=window)
                    rows = scraper.collect_one(page, route.origin, route.destination, departure)
                    out.append((route, window, rows))
        finally:
            browser.close()
    return out


# ---------------------------------------------------------------------------
# pipeline: blend with the baseline, run the unmodified cleaning + index code
# ---------------------------------------------------------------------------


def data_mode_shares(raw: pd.DataFrame) -> dict[str, float]:
    if raw.empty or "data_mode" not in raw.columns:
        return {"real": 0.0, "synthetic": 0.0}
    counts = raw["data_mode"].value_counts()
    total = float(counts.sum())
    return {
        "real": round(float(counts.get("real", 0)) / total, 4),
        "synthetic": round(float(counts.get("synthetic", 0)) / total, 4),
    }


def run_pipeline_and_report(baseline_raw: pd.DataFrame, combined_raw: pd.DataFrame) -> None:
    """Print the before/after shift and run the index once, unmodified."""
    print(f"\n{'=' * 72}\nBEFORE  (45-day seeded baseline only)\n{'=' * 72}")
    before_shares = data_mode_shares(baseline_raw)
    print(f"  rows: {len(baseline_raw)}   data_mode: {before_shares}")

    print(f"\n{'=' * 72}\nAFTER  (baseline + this run's live batch)\n{'=' * 72}")
    after_shares = data_mode_shares(combined_raw)
    print(f"  rows: {len(combined_raw)}   data_mode: {after_shares}")

    if after_shares["real"] <= before_shares["real"]:
        print(
            "\n  NOTE: real share did not increase. If the source's rows landed as "
            "data_mode='synthetic' (e.g. a Duffel TEST token), that is the collector "
            "correctly reporting simulated inventory, not a bug — see this script's "
            "module docstring."
        )

    # DEMO-ONLY deviation from production behavior, and worth being explicit
    # about: `clean()` normally excludes any row captured outside a narrow
    # window around the fixed daily index slot (06:30 IST +/- 45min) — correct
    # for production, where a drifting capture time is collection noise, not
    # inflation. A stage demo runs at whatever time the slot in the agenda is,
    # which is essentially never inside that window. Enforcing it here would
    # silently exclude every live row from data_mode_breakdown, killing the
    # entire "watch the banner shift" beat while LOOKING like it worked (the
    # rows print, they insert into SQLite, they just never reach the index).
    # `enforce_slot=False` is passed ONLY in this demo script — never in
    # aipi.pipeline or the production path.
    cleaned = clean(combined_raw, enforce_slot=False)
    rep = cleaned.report
    print(f"\ncleaning: {rep.rows_in} in -> {rep.rows_index_eligible} index-eligible "
          f"({rep.retention_pct:.1f}%), lineage={rep.data_mode_breakdown}")

    weight_set = load_weights()
    idx = compute_index(cleaned.index_input, route_weights=weight_set.weights)
    dates = idx.dates
    print(f"index: {len(idx.headline)} daily points, latest {dates[-1]} = "
          f"{idx.headline[dates[-1]]:.4f}")

    LIVE_DEMO_DIR.mkdir(parents=True, exist_ok=True)
    combined_raw.to_parquet(BLENDED_PATH, index=False)
    print(f"\nwrote {BLENDED_PATH}")
    print(
        "Restart the API to serve this blend (see docs/LIVE_DEMO_RUNBOOK.md):\n"
        "  docker compose restart api\n"
        "  # or, running from source: Ctrl-C the uvicorn process and start it again"
    )


# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="Live demo: small, fast, real collection")
    ap.add_argument("--source", choices=("duffel", "scrape"), default="duffel")
    ap.add_argument(
        "--scraper", default="spicejet_site",
        help="scraper SOURCE_NAME to use with --source scrape (see scripts/check_demo_sources.py)",
    )
    args = ap.parse_args()

    LIVE_DEMO_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    conn = sqlite3.connect(DB_PATH)
    _ensure_db(conn)

    print(f"Live demo run {run_id}")
    print(f"  routes:  {[r.route_code for r in DEMO_ROUTES]}")
    print(f"  windows: {DEMO_WINDOWS}")
    print(f"  source:  {args.source}" + (f" ({args.scraper})" if args.source == "scrape" else ""))
    print()

    t0 = time.monotonic()
    batch_rows: list[dict] = []

    try:
        if args.source == "duffel":
            capture_ts = datetime.now(UTC)
            for route in DEMO_ROUTES:
                for window in DEMO_WINDOWS:
                    rows = collect_duffel_cell(route, window, capture_ts)
                    for row in rows:
                        _print_row(row)
                        _insert_row(conn, row, run_id)
                        batch_rows.append(row)
        else:
            for route, window, rows in collect_scrape_cells(args.scraper):
                for row in rows:
                    _print_row(row)
                    _insert_row(conn, row, run_id)
                    batch_rows.append(row)
    except CollectionError as exc:
        elapsed = time.monotonic() - t0
        print(f"\nFAILED after {elapsed:.1f}s: {exc}")
        print(
            "This is the documented fallback trigger — see docs/LIVE_DEMO_RUNBOOK.md "
            "'If live collection fails on stage'. Do not silently substitute synthetic "
            "rows for this run; acknowledge the failure and continue from the seeded "
            "baseline."
        )
        return 1
    finally:
        conn.close()

    elapsed = time.monotonic() - t0
    print(f"\ncollected {len(batch_rows)} row(s) in {elapsed:.1f}s")
    if elapsed > 60:
        print("WARNING: exceeded the 60s demo budget — reconsider source/scope before stage.")

    if not batch_rows:
        print(
            "\nZero rows collected (all cells sold out, or every cell failed silently). "
            "Treat this the same as a collection failure for the demo: fall back per "
            "docs/LIVE_DEMO_RUNBOOK.md rather than presenting an empty blend."
        )
        return 1

    # Must match aipi.api.deps._bootstrap_demo_store's baseline exactly (same
    # function, same day count) — otherwise "before" here and what a freshly
    # booted API actually serves would silently diverge.
    baseline_raw = default_demo_frame(n_days=45)
    live_df = pd.DataFrame(batch_rows, columns=list(RAW_COLUMNS))
    combined_raw = pd.concat([baseline_raw, live_df], ignore_index=True)
    run_pipeline_and_report(baseline_raw, combined_raw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
