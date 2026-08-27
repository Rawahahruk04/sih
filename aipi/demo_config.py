"""Live-demo scope. NOT the production basket — see the module docstring on why.

`aipi.basket` defines the full system: 12 routes, 5 mandated advance-purchase
windows. Running that live on stage is the wrong instrument for a demo: more
routes/windows means more requests, more chances for one slow site or one
rate-limit to stall the room while an audience watches a spinner.

This module is a small, explicit, SEPARATE scope for exactly one purpose —
proving the mechanism live, at low cardinality, quickly. Nobody should be able
to look at a live-demo run and mistake it for a claim about basket coverage;
keeping it in its own file with its own name (`DEMO_ROUTES`, not `SAMPLE_ROUTES`)
makes that confusion harder to make by accident.

Source selection is deliberately NOT hardcoded here. Which source is "the demo
source" depends on what is actually reachable on the day — see
`scripts/check_demo_sources.py` and `docs/LIVE_DEMO_RUNBOOK.md`. Hardcoding a
scraper class that turns out to be CAPTCHA-gated on demo day is exactly the
failure mode this file exists to avoid.
"""

from __future__ import annotations

from aipi.basket import SAMPLE_ROUTES, Route

#: Two PS-named, high-traffic routes. Enough to show the heatmap and the route
#: breakdown have more than one row without paying for a third site's latency.
DEMO_ROUTE_CODES: tuple[str, ...] = ("DEL-BOM", "DEL-BLR")

DEMO_ROUTES: tuple[Route, ...] = tuple(
    r for r in SAMPLE_ROUTES if r.route_code in DEMO_ROUTE_CODES
)
assert len(DEMO_ROUTES) == len(DEMO_ROUTE_CODES), (
    "a DEMO_ROUTE_CODES entry does not match any route in aipi.basket.SAMPLE_ROUTES"
)

#: Two of the five PS-mandated windows. T+7 (near-term) and T+30 (planned) give a
#: visible lead-time gap without collecting all five.
DEMO_WINDOWS: tuple[int, ...] = (7, 30)

#: Kept for documentation/printing only — the actual source used on any given
#: run is resolved at runtime by scripts/run_live_demo.py against whatever
#: currently passes scripts/check_demo_sources.py. Do not import this as if it
#: were a guarantee.
DEMO_SOURCE_CANDIDATES: tuple[str, ...] = ("duffel", "spicejet_site", "akasa_site")
