"""Seed 45 days of labelled synthetic data so the API is fully populated offline.

Purpose
-------
The frontend cannot wait for live scraping, ToS reviews, or 30 days of real
collection. This script produces a complete, realistic, fully-labelled dataset
with **no internet dependency**, so `docker-compose up` yields a working API
immediately. It is also the demo-day fallback if the venue network fails.

Two disciplines that make this defensible rather than a cheat
--------------------------------------------------------------
1. **Every row is labelled `data_mode='synthetic'`.** The API aggregates that
   label into `/health`, so the dashboard can render an honest "demo data"
   banner. Synthetic rows and real rows are never indistinguishable.

2. **The DGCA reference is NOT derived from the same anchors as the fares.**
   Generating both from one set of numbers would make the backtest a tautology:
   it would report a near-perfect correlation that proves only that two outputs
   of the same generator agree. Instead the reference is built with independent
   measurement noise and a partly independent trend, so the backtest exercises
   a real comparison and returns a plausible — not perfect — r. A backtest that
   always returns r≈1.0 is worse than no backtest, because it looks like
   evidence.

Idempotent: re-running replaces only `data_mode='synthetic'` rows and never
touches real collected data.

    python -m scripts.seed_synthetic              # 45 days, default seed
    python -m scripts.seed_synthetic --days 60
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from aipi.basket import SAMPLE_ROUTES
from aipi.cleaning import clean
from aipi.collectors.synthetic import (
    SyntheticConfig,
    generate,
    inject_dirty_rows,
    slot_drift_rows,
)
from aipi.index.engine import compute_index
from aipi.weights import load_weights

OUT_DIR = Path("data/out")
SEED_DIR = Path("data/seed")

#: Independent noise applied when deriving the DGCA reference, so the backtest
#: is a real comparison rather than a restatement of the generator.
DGCA_MEASUREMENT_NOISE_SD = 0.035
#: Fraction of the reference's trend that is INDEPENDENT of the fare generator's.
#: At 0.0 the reference is a pure function of the fares (tautological backtest);
#: at 1.0 it is unrelated noise. A real statistical office measuring the same
#: underlying market with a different method lands somewhere in between.
DGCA_INDEPENDENT_TREND_SHARE = 0.30


def build_dgca_reference(
    clean_fares: pd.DataFrame, *, seed: int
) -> pd.DataFrame:
    """Monthly average fare per route, as a DGCA-like external reference.

    Deliberately built with its own noise and a partly independent trend — see
    the module docstring on why a reference derived cleanly from the same
    generator would make the backtest meaningless.
    """
    rng = np.random.default_rng(seed + 9001)
    df = clean_fares.copy()
    df = df[df["total_fare"].notna() & (df["total_fare"] > 0)]
    if df.empty:
        return pd.DataFrame(columns=["period", "route_code", "avg_fare", "passengers"])

    df["period"] = pd.to_datetime(df["capture_date"]).dt.strftime("%Y-%m")
    grouped = (
        df.groupby(["period", "route_code"])["total_fare"].mean().reset_index()
    )

    # A statistical office measuring the same market with a different instrument
    # (ticket sales rather than quoted fares) sees a correlated but not identical
    # series. Model that explicitly rather than pretending the two coincide.
    n = len(grouped)
    noise = rng.normal(0.0, DGCA_MEASUREMENT_NOISE_SD, size=n)
    independent = rng.normal(0.0, DGCA_MEASUREMENT_NOISE_SD * 2.0, size=n)
    factor = np.exp(
        (1.0 - DGCA_INDEPENDENT_TREND_SHARE) * noise
        + DGCA_INDEPENDENT_TREND_SHARE * independent
    )
    grouped["avg_fare"] = (grouped["total_fare"] * factor).round(2)
    grouped = grouped.drop(columns=["total_fare"])
    grouped["passengers"] = None
    grouped["is_placeholder"] = True
    grouped["source_note"] = (
        "SYNTHETIC reference derived from seeded fares with independent "
        "measurement noise. NOT DGCA data."
    )
    return grouped


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(description="Seed synthetic AIPI data for the API")
    ap.add_argument("--days", type=int, default=45, help="collection days to generate")
    ap.add_argument("--seed", type=int, default=20260826)
    ap.add_argument(
        "--end",
        type=str,
        default=None,
        help="last capture date (ISO); defaults to yesterday so the series looks current",
    )
    ap.add_argument("--out", type=str, default=str(SEED_DIR))
    args = ap.parse_args()

    end = date.fromisoformat(args.end) if args.end else date.today() - timedelta(days=1)
    start = end - timedelta(days=args.days - 1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    logging.info("generating %d days: %s .. %s", args.days, start, end)

    cfg = SyntheticConfig(
        start=start,
        n_days=args.days,
        seed=args.seed,
        calibration_months=(),  # nothing is calibrated to the reference; see docstring
    )
    raw = generate(cfg)
    raw = inject_dirty_rows(raw, seed=args.seed + 1)
    raw = slot_drift_rows(raw, seed=args.seed + 2)

    logging.info("raw rows: %d", len(raw))

    result = clean(raw)
    rep = result.report
    logging.info(
        "cleaned: %d in -> %d index-eligible (%.1f%% retention)",
        rep.rows_in, rep.rows_index_eligible, rep.retention_pct,
    )

    weight_set = load_weights()
    if weight_set.is_placeholder:
        logging.warning(
            "weights are PLACEHOLDER figures, not DGCA — every derived number "
            "inherits that label"
        )

    idx = compute_index(result.index_input, route_weights=weight_set.weights)
    dates = idx.dates
    logging.info(
        "index: %d daily points, %s = %.3f",
        len(idx.headline), dates[-1], idx.headline[dates[-1]],
    )

    dgca = build_dgca_reference(result.index_input, seed=args.seed)
    logging.info("dgca reference: %d route-months", len(dgca))

    # --- persist ------------------------------------------------------------
    result.clean_fares.to_parquet(out_dir / "clean_fares.parquet", index=False)
    dgca.to_parquet(out_dir / "dgca_reference.parquet", index=False)

    manifest = {
        "generated_for": "frontend development and offline demo",
        "data_mode": "synthetic",
        "warning": (
            "Every row here is simulated. Nothing in this directory is a "
            "measurement of any real airfare."
        ),
        "days": args.days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "seed": args.seed,
        "routes": [r.route_code for r in SAMPLE_ROUTES],
        "weights": weight_set.to_dict(),
        "index": {
            "daily_points": len(idx.headline),
            "weekly_points": len(idx.weekly.series) if idx.weekly else 0,
            "monthly_points": len(idx.monthly.series) if idx.monthly else 0,
            "base_period": [d.isoformat() for d in idx.base_periods],
            "latest": {
                "date": dates[-1].isoformat(),
                "headline": round(idx.headline[dates[-1]], 4),
            },
        },
        "dgca_reference_route_months": len(dgca),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    logging.info("wrote %s", out_dir)
    logging.info(
        "ALL SEEDED DATA IS SYNTHETIC — /health reports data_mode so the "
        "dashboard can say so too"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
