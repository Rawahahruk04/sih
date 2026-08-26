"""Inspect the current contents of the AIPI store/database."""
import json
import pandas as pd
from aipi.api.deps import get_store

store = get_store()
meta = store.methodology()
run = store.pipeline_run()
routes = store.list_routes()
headline = store.headline(freq="daily")
weekly = store.headline(freq="weekly")
monthly = store.headline(freq="monthly")
curve = store.leadtime_price_curve()
val = store.validation()
vol = store.volatility()

print("=" * 80)
print("AIPI DATABASE / STORE CONTENT AUDIT")
print("=" * 80)
print(f"Pipeline Run ID:         {run.get('run_id')}")
print(f"Code Version & Git SHA:  {run.get('code_version')} ({run.get('git_sha')})")
print(f"Total Raw Observations:  {run.get('input_row_count'):,} fare quotes")
print(f"Index-Eligible Cleaned:  {run.get('index_eligible_rows'):,} fare quotes")
print(f"Active Basket Routes:    {len(routes)} city pairs")
print(f"Base Period (100.0):     {meta.get('base_period', {}).get('start')} to {meta.get('base_period', {}).get('end')}")
print(f"Date Span:               {headline[0]['date']} to {headline[-1]['date']} ({len(headline)} daily points)")
print(f"Data Mode / Lineage:     {store.data_mode_summary()}")

print("\n" + "-" * 80)
print("1. ROUTE BASKET & LASPEYRES EXPENDITURE WEIGHTS")
print("-" * 80)
for r in routes:
    print(f"  {r['route_code']:<8} ({r['display_name']:<24}) -> Weight: {r['weight']:>6.2%} | Latest Index: {r['latest_value']:>6.2f} ({r['latest_date']})")

print("\n" + "-" * 80)
print("2. ADVANCE-PURCHASE PRICE ELASTICITY CURVE (LATEST DATE)")
print("-" * 80)
print(f"Anchor Window: T+{curve.get('reference_window')} days = 100.0")
for pt in curve.get("curve", []):
    diff = pt['relative_level'] - 100.0
    sign = "+" if diff >= 0 else ""
    print(f"  T+{pt['advance_days']:>2} booking window: Relative Fare Level = {pt['relative_level']:>6.2f} ({sign}{diff:.1f}% vs reference)")

print("\n" + "-" * 80)
print("3. PUBLISHED INDEX SERIES SUMMARY")
print("-" * 80)
print(f"  • Daily Headline:    {len(headline)} points ({headline[0]['date']} to {headline[-1]['date']})")
print(f"  • Weekly Headline:   {len(weekly)} points")
print(f"  • Monthly Headline:  {len(monthly)} points")
print("\nSample Daily Points:")
for pt in headline[:3] + headline[-3:]:
    print(f"    {pt['date']} -> Index: {pt['value']:>6.2f} | Obs: {pt['n_obs']:>3} | Coverage: {pt['coverage_pct']:>5.1f}% | Matched Pairs: {pt.get('matched_n')}")

print("\n" + "-" * 80)
print("4. DGCA BACKTEST VALIDATION PANEL")
print("-" * 80)
panel = val.get("route_month_panel", {})
print(f"  • Primary Comparison:       {val.get('primary_comparison')}")
print(f"  • Route-Month Sample (n):   {panel.get('n', 'N/A')}")
print(f"  • Directional Accuracy:     {f'{panel.get('directional_accuracy'):.1%}' if panel.get('directional_accuracy') is not None else 'N/A'}")
print(f"  • MAPE on MoM Movements:    {f'{panel.get('mape_pct'):.1f}%' if panel.get('mape_pct') is not None else 'N/A'}")
print(f"  • Spearman Rank Corr:       {panel.get('spearman_rho', 'N/A')}")
print(f"  • Daily Fare Volatility:    {f'{val.get('construct_validity', {}).get('daily_volatility_pct'):.2f}%' if val.get('construct_validity') else 'N/A'}")
print(f"  • Lead-time Monotonicity:   {'✅ Monotone Decreasing' if val.get('construct_validity', {}).get('leadtime_monotone_decreasing') else 'N/A'}")

print("=" * 80)
