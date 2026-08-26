"""End-to-end pipeline: collect (or generate) -> clean -> index -> validate.

Run with no arguments for the full offline demo:

    python -m scripts.run_pipeline

Everything is deterministic given ``--seed``, so a printed number can be
reproduced exactly — a requirement for anything presented as a statistic.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pandas as pd

from aipi.basket import AUXILIARY_CAPTURE_SLOTS, REFERENCE_WINDOW
from aipi.cleaning import clean
from aipi.collectors.synthetic import (
    SyntheticConfig,
    capture_slot_variants,
    default_demo_frame,
    demo_base_fares,
    demo_passengers,
    generate,
    inject_dirty_rows,
)
from aipi.index.aggregate import expenditure_weights, quantity_weights, weight_divergence
from aipi.index.engine import compute_index
from aipi.validation.backtest import construct_validity_checks
from aipi.validation.measurement_error import (
    required_sampling_days,
    sampling_error_curve,
    simulate_monthly_sampling,
)

OUT_DIR = Path("data/out")


def main() -> int:
    ap = argparse.ArgumentParser(description="AIPI end-to-end pipeline")
    ap.add_argument("--days", type=int, default=75)
    ap.add_argument("--start", type=str, default="2026-06-01")
    ap.add_argument("--seed", type=int, default=20260826)
    ap.add_argument("--intraday", action="store_true", help="add auxiliary capture slots")
    ap.add_argument("--clean-only", action="store_true")
    ap.add_argument("--out", type=str, default=str(OUT_DIR))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. collect ---------------------------------------------------------
    start = date.fromisoformat(args.start)
    if args.intraday:
        cfg = SyntheticConfig(start=start, n_days=args.days, seed=args.seed)
        raw = capture_slot_variants(generate(cfg), AUXILIARY_CAPTURE_SLOTS)
        raw = inject_dirty_rows(raw)
    else:
        raw = default_demo_frame(start=start, n_days=args.days, seed=args.seed)

    print(f"\n{'=' * 72}\nCOLLECTION\n{'=' * 72}")
    print(f"raw rows                 {len(raw):>10,}")
    print(f"capture dates            {raw['capture_date'].nunique():>10,}")
    print(f"routes                   {raw['origin'].nunique() * 1:>10,} origins")

    # ---- 2. clean -----------------------------------------------------------
    result = clean(raw)
    rep = result.report
    print(f"\n{'=' * 72}\nCLEANING\n{'=' * 72}")
    print(f"rows in                  {rep.rows_in:>10,}")
    print(f"quarantined              {rep.rows_quarantined:>10,}   {rep.quarantine_reasons}")
    print(f"off index capture slot   {rep.rows_off_capture_slot:>10,}")
    print(f"basket exclusions        {'':>10}   {rep.basket_exclusions}")
    print(f"de-duplicated            {rep.rows_deduplicated:>10,}")
    print(f"sold out (flagged)       {rep.rows_soldout:>10,}")
    print(f"tax split imputed        {rep.split_imputation.get('rows_with_imputed_split', 0):>10,}")
    print(
        f"  split model            {rep.split_model.get('method')} "
        f"R2={rep.split_model.get('r_squared', 0):.4f} n={rep.split_model.get('n_fitted')}"
    )
    print(f"outliers flagged         {rep.outliers.get('flagged', 0):>10,}")
    print(f"  cells untrimmed (n<8)  {rep.outliers.get('cells_skipped_small_n', 0):>10,}")
    print(f"index-eligible rows      {rep.rows_index_eligible:>10,}   ({rep.retention_pct:.1f}%)")

    result.clean_fares.to_parquet(out_dir / "clean_fares.parquet", index=False)
    result.quarantined.to_csv(out_dir / "quarantined.csv", index=False)

    if args.clean_only:
        return 0

    # ---- 3. weights ---------------------------------------------------------
    passengers = demo_passengers()
    base_fares = demo_base_fares()
    exp_w = expenditure_weights(passengers, base_fares)
    qty_w = quantity_weights(passengers)
    div = weight_divergence(exp_w, qty_w)

    print(f"\n{'=' * 72}\nWEIGHTS  (Laspeyres = base-period EXPENDITURE shares)\n{'=' * 72}")
    print(f"{'route':<10}{'expenditure':>14}{'passenger':>12}{'diff (bps)':>13}")
    for r in sorted(exp_w, key=lambda k: -exp_w[k]):
        print(f"{r:<10}{exp_w[r]:>14.5f}{qty_w[r]:>12.5f}{div[r]:>13.0f}")

    # ---- 4. index -----------------------------------------------------------
    idx = compute_index(result.index_input, route_weights=exp_w)
    wrong = compute_index(result.index_input, route_weights=qty_w)

    print(f"\n{'=' * 72}\nINDEX\n{'=' * 72}")
    print(f"base period              {idx.base_periods[0]} .. {idx.base_periods[-1]} "
          f"({len(idx.base_periods)} days, geometric mean = 100)")
    print(f"days published           {len(idx.headline):>10,}")
    print(f"cells                    {len(idx.cell_index):>10,}")
    dates = idx.dates
    print(f"headline {dates[0]}      {idx.headline[dates[0]]:>10.3f}")
    print(f"headline {dates[-1]}      {idx.headline[dates[-1]]:>10.3f}")
    print(f"  DOW-adjusted           {idx.headline_dow_adjusted[dates[-1]]:>10.3f}")
    print(f"  n obs (last day)       {idx.n_obs.get(dates[-1], 0):>10,}")
    print(f"  matched n (last day)   {idx.matched_n.get(dates[-1], 0):>10,}")
    print(f"  coverage (last day)    {idx.coverage.get(dates[-1], 0):>10.3f}")

    print("\nspecification diagnostics")
    print(f"  DOW amplitude          {idx.dow_amplitude_pct:>10.2f}%  (weekly cycle removed)")
    print(f"  chain drift removed    {idx.chain_drift.get('end_gap_pct', 0):>10.3f}%  "
          "(chained vs GEKS at series end)")
    print(f"  max chain drift        {idx.chain_drift.get('max_abs_gap_pct', 0):>10.3f}%")
    print(f"  composition bias       {idx.composition_bias_pct:>10.3f}%  "
          "(GM-of-levels vs matched)")
    gap = idx.headline[dates[-1]] - wrong.headline[dates[-1]]
    move = idx.headline[dates[-1]] - 100.0
    share = abs(gap) / abs(move) * 100.0 if abs(move) > 1e-9 else float("nan")
    print(f"  weight spec impact     {gap:>10.3f}   index points "
          "(expenditure minus passenger weights)")
    print(f"    as share of movement {share:>10.1f}%  "
          f"(headline has moved {move:+.3f} points from base)")
    for note in idx.notes[:6]:
        print(f"  note: {note}")

    print("\nday-of-week factors")
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    print("  " + "".join(f"{n:>8}" for n in names))
    print("  " + "".join(f"{idx.dow_factors[d]:>8.4f}" for d in range(7)))

    print(
        f"\nlead-time PRICE curve (relative fare level, "
        f"{REFERENCE_WINDOW}-day window = 100)"
    )
    if idx.leadtime_price_curve:
        latest = max(idx.leadtime_price_curve)
        curve = idx.leadtime_price_curve[latest]
        for window in sorted(curve, reverse=True):
            print(f"  {window:>3}d before departure  {curve[window]:>10.2f}")
        print(f"  (as at {latest})")

    print("\nlead-time INDEX by window (base period = 100; inflation, not level)")
    for window, series in sorted(idx.leadtime_index.items()):
        if series:
            print(f"  {window:>3}d out               {series[max(series)]:>10.3f}")

    # ---- frequencies (PS-mandated daily / weekly / monthly) -----------------
    print(f"\n{'=' * 72}\nPUBLISHED FREQUENCIES\n{'=' * 72}")
    print(f"daily      {len(idx.headline):>4} points")
    for label, res in (("weekly", idx.weekly), ("monthly", idx.monthly)):
        if res is None or not res.series:
            continue
        periods = sorted(res.series)
        print(f"{label:<11}{len(periods):>4} points   "
              f"latest {periods[-1]} = {res.series[periods[-1]]:.3f}")
        pop = res.period_on_period_pct()
        if pop:
            last = max(pop)
            print(f"{'':11}     period-on-period at {last}: {pop[last]:+.3f}%")
        print(f"{'':11}     mean gap vs naive mean-of-levels: "
              f"{res.mean_abs_gap:.4f} index points")

    # ---- 5. validation ------------------------------------------------------
    print(f"\n{'=' * 72}\nMEASUREMENT ERROR OF THE CURRENT MONTHLY PROCESS\n{'=' * 72}")
    try:
        me1 = simulate_monthly_sampling(idx.headline, days_per_month=1)
        print(f"\n  {me1.headline_sentence()}\n")
        print(f"{'days/month':>12}{'MAE %':>10}{'p95 |err| %':>14}{'wrong direction':>18}")
        for row in sampling_error_curve(idx.headline):
            print(
                f"{row['days_per_month']:>12}{row['mae_pct']:>10.3f}"
                f"{row['p95_abs_pct']:>14.3f}{row['direction_error_rate'] * 100:>17.1f}%"
            )
        req = required_sampling_days(idx.headline, target_mae_pct=1.0)
        if req["achieved"]:
            print(
                f"\n  To reach +/-1% MAE by sparse sampling, the current design would need "
                f"{req['required_days_per_month']} collection day(s) per month."
            )
        else:
            print("\n  +/-1% MAE was not reached at any tested sampling intensity.")
        me_payload = {
            "one_day_per_month": me1.to_dict(),
            "curve": sampling_error_curve(idx.headline),
            "required_days": req,
        }
    except ValueError as exc:
        print(f"  not computable: {exc}")
        me_payload = {"error": str(exc)}

    print(f"\n{'=' * 72}\nCONSTRUCT VALIDITY\n{'=' * 72}")
    checks = construct_validity_checks(
        idx.headline, leadtime_price_curve=idx.leadtime_price_curve
    )
    for k, v in checks.items():
        print(f"  {k:<34}{v}")
    if checks.get("suspiciously_flat"):
        print("  !! index does not move — collector is almost certainly serving cached data")

    # ---- 6. persist ---------------------------------------------------------
    payload = {
        "base_periods": [d.isoformat() for d in idx.base_periods],
        "headline": {d.isoformat(): round(v, 4) for d, v in sorted(idx.headline.items())},
        "headline_dow_adjusted": {
            d.isoformat(): round(v, 4) for d, v in sorted(idx.headline_dow_adjusted.items())
        },
        "headline_tornqvist": {
            d.isoformat(): round(v, 4) for d, v in sorted(idx.headline_tornqvist.items())
        },
        "formula_spread": idx.formula_spread,
        "weekly": (
            {d.isoformat(): round(v, 4) for d, v in sorted(idx.weekly.series.items())}
            if idx.weekly
            else {}
        ),
        "monthly": (
            {d.isoformat(): round(v, 4) for d, v in sorted(idx.monthly.series.items())}
            if idx.monthly
            else {}
        ),
        "n_obs": {d.isoformat(): v for d, v in sorted(idx.n_obs.items())},
        "coverage": {d.isoformat(): round(v, 4) for d, v in sorted(idx.coverage.items())},
        "route_index": {
            r: {d.isoformat(): round(v, 4) for d, v in sorted(s.items())}
            for r, s in idx.route_index.items()
        },
        "leadtime_index": {
            str(w): {d.isoformat(): round(v, 4) for d, v in sorted(s.items())}
            for w, s in idx.leadtime_index.items()
        },
        "leadtime_price_curve": {
            d.isoformat(): {str(w): round(v, 4) for w, v in sorted(c.items())}
            for d, c in sorted(idx.leadtime_price_curve.items())
        },
        "dow_factors": {str(k): round(v, 6) for k, v in idx.dow_factors.items()},
        "diagnostics": {
            "dow_amplitude_pct": round(idx.dow_amplitude_pct, 4),
            "chain_drift": idx.chain_drift,
            "composition_bias_pct": round(idx.composition_bias_pct, 4),
            "weight_spec_gap_index_points": round(gap, 4),
            "weight_spec_gap_share_of_movement_pct": round(share, 2),
        },
        "route_weights": {k: round(v, 6) for k, v in idx.route_weights.items()},
        "cleaning_report": rep.to_dict(),
        "measurement_error": me_payload,
        "construct_validity": checks,
        "notes": idx.notes,
    }
    (out_dir / "index.json").write_text(json.dumps(payload, indent=2, default=str))

    pd.DataFrame(
        [{"index_date": d, "headline_index": v} for d, v in sorted(idx.headline.items())]
    ).to_csv(out_dir / "index_daily.csv", index=False)

    print(f"\nwrote {out_dir / 'index.json'}, index_daily.csv, clean_fares.parquet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
