"""Single CLI entrypoint: collect -> clean -> index -> validate.

    python -m aipi.pipeline run --source synthetic
    python -m aipi.pipeline run --source scrape --with-otas
    python -m aipi.pipeline run --source parquet --input data/raw

Idempotent for a given date: re-running overwrites that date's outputs rather
than appending, so a retried job cannot double-count. The raw captures under
`data/raw/` are never rewritten — only the derived index is.

The seed generator is deliberately NOT reachable from here. It is a separate
manual command (`scripts/seed_synthetic.py`) precisely so a scheduled production
run can never accidentally mix synthetic rows into a real series.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from aipi.cleaning import clean
from aipi.index.engine import compute_index
from aipi.validation.cpi_reference import CpiReferenceError, load_cpi_reference
from aipi.validation.report import build_validation_report, write_report
from aipi.weights import load_weights

log = logging.getLogger("aipi.pipeline")

RAW_DIR = Path("data/raw")
OUT_DIR = Path("data/out")


class PipelineError(RuntimeError):
    """The run failed in a way that must not produce published output."""


def _load_raw(source: str, input_dir: Path, days: int, seed: int) -> pd.DataFrame:
    if source == "synthetic":
        from datetime import timedelta

        from aipi.collectors.synthetic import (
            SyntheticConfig,
            generate,
            inject_dirty_rows,
            slot_drift_rows,
        )

        end = date.today() - timedelta(days=1)
        cfg = SyntheticConfig(start=end - timedelta(days=days - 1), n_days=days, seed=seed)
        raw = slot_drift_rows(inject_dirty_rows(generate(cfg), seed=seed + 1), seed=seed + 2)
        log.warning("source=synthetic: every row is simulated and labelled as such")
        return raw

    if source == "parquet":
        files = sorted(input_dir.glob("*.parquet"))
        if not files:
            raise PipelineError(
                f"no parquet captures found in {input_dir}. Run a collector first "
                "(scripts/run_scrape.py) or pass --source synthetic."
            )
        log.info("reading %d capture file(s) from %s", len(files), input_dir)
        return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    if source == "scrape":
        from aipi.collectors.scraper.collect import collect

        return collect()

    if source == "duffel":
        from aipi.collectors.duffel import collect as duffel_collect

        return duffel_collect()

    raise PipelineError(f"unknown source: {source!r}")


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- collect ---------------------------------------------------------
    raw = _load_raw(args.source, Path(args.input), args.days, args.seed)
    log.info("raw rows: %d", len(raw))
    if raw.empty:
        raise PipelineError("collection produced zero rows; refusing to publish")

    # --- clean -----------------------------------------------------------
    cleaned = clean(raw)
    rep = cleaned.report
    log.info(
        "cleaned: %d -> %d index-eligible (%.1f%%), lineage=%s",
        rep.rows_in, rep.rows_index_eligible, rep.retention_pct, rep.data_mode_breakdown,
    )
    if rep.rows_index_eligible == 0:
        raise PipelineError(
            "no index-eligible rows survived cleaning. Publishing nothing is correct; "
            f"quarantine reasons: {rep.quarantine_reasons}"
        )

    # --- weights ---------------------------------------------------------
    weight_set = load_weights(args.weights)
    if weight_set.is_placeholder and not args.allow_placeholder_weights:
        raise PipelineError(
            "route weights are PLACEHOLDER figures, not DGCA. Pass "
            "--allow-placeholder-weights to proceed for a demo run, but do not "
            "present the output as a statistic."
        )

    # --- index -----------------------------------------------------------
    idx = compute_index(cleaned.index_input, route_weights=weight_set.weights)
    dates = idx.dates
    log.info("index: %d daily points, latest %s = %.4f",
             len(idx.headline), dates[-1], idx.headline[dates[-1]])

    # --- validate --------------------------------------------------------
    report = None
    ref_path = Path(args.reference) if args.reference else None
    if ref_path and ref_path.exists():
        reference = pd.read_parquet(ref_path)
        cpi = None
        try:
            cpi = load_cpi_reference()
            log.info(
                "CPI reference: %d months %s..%s (real=%s)",
                len(cpi.series), cpi.first_period, cpi.last_period,
                not cpi.is_placeholder,
            )
        except CpiReferenceError as exc:
            log.warning("CPI reference unavailable: %s", exc)
        report = build_validation_report(
            daily_index=idx.headline,
            route_index=idx.route_index,
            reference=reference,
            route_weights=weight_set.weights,
            contributing_rows=cleaned.index_input,
            leadtime_price_curve=idx.leadtime_price_curve,
            cpi_reference=cpi,
        )
        write_report(report, out_dir)
        log.info("validation: %s", report.headline_caveat())
    else:
        log.info("no reference series supplied; validation skipped (not failed)")

    # --- persist ---------------------------------------------------------
    cleaned.clean_fares.to_parquet(out_dir / "clean_fares.parquet", index=False)
    cleaned.quarantined.to_csv(out_dir / "quarantined.csv", index=False)
    pd.DataFrame(
        [{"index_date": d, "headline_index": v} for d, v in sorted(idx.headline.items())]
    ).to_csv(out_dir / "index_daily.csv", index=False)

    summary = {
        "run_at": datetime.now(UTC).isoformat(),
        "source": args.source,
        "data_mode_breakdown": rep.data_mode_breakdown,
        "weights_are_placeholder": weight_set.is_placeholder,
        "daily_points": len(idx.headline),
        "weekly_points": len(idx.weekly.series) if idx.weekly else 0,
        "monthly_points": len(idx.monthly.series) if idx.monthly else 0,
        "latest": {"date": dates[-1].isoformat(), "value": round(idx.headline[dates[-1]], 4)},
        "cleaning": rep.to_dict(),
        "validation_available": report is not None,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    log.info("wrote %s", out_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    ap = argparse.ArgumentParser(prog="aipi.pipeline", description="AIPI pipeline")
    sub = ap.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="collect -> clean -> index -> validate")
    r.add_argument(
        "--source",
        choices=("synthetic", "parquet", "scrape", "duffel"),
        default="parquet",
        help="parquet reads previously-collected captures; scrape collects live",
    )
    r.add_argument("--input", default=str(RAW_DIR), help="capture directory for --source parquet")
    r.add_argument("--out", default=str(OUT_DIR))
    r.add_argument("--reference", default="data/seed/dgca_reference.parquet")
    r.add_argument("--weights", default=None, help="path to a DGCA traffic file")
    r.add_argument("--days", type=int, default=45, help="--source synthetic only")
    r.add_argument("--seed", type=int, default=20260826)
    r.add_argument(
        "--allow-placeholder-weights",
        action="store_true",
        help="proceed even though weights are not real DGCA figures (demo runs only)",
    )
    r.set_defaults(func=run)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except PipelineError as exc:
        log.error("pipeline failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
