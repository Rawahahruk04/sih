"""Store wiring for the API.

The store is a process-level singleton, resolved lazily. Tests and the production
entrypoint override it with `configure_store(...)`; if nothing overrides it, the API
bootstraps the zero-dependency demo store from synthetic data, so a bare `uvicorn
aipi.api:app` comes up with a working index and needs no database.
"""

from __future__ import annotations

import logging
import threading

from aipi.store import IndexStore, SnapshotStore, build_snapshot

log = logging.getLogger(__name__)

_store: IndexStore | None = None

#: Building the demo snapshot takes ~11s (generate -> clean -> index -> validate).
#: Without a lock, N concurrent first requests would each start their own build —
#: a thundering herd that wastes CPU and, worse, leaves whichever finishes last
#: as the installed store. The API is warmed at startup (see `main.lifespan`), so
#: this lock is the belt to that braces.
_lock = threading.Lock()


def configure_store(store: IndexStore) -> None:
    """Install the store the API should read from (production wiring, or a test)."""
    global _store
    with _lock:
        _store = store


def is_configured() -> bool:
    """True once a store exists, so startup can skip redundant warm-up."""
    return _store is not None


#: Written by scripts/run_live_demo.py: the 45-day synthetic baseline blended
#: with whatever real rows the live-demo run collected. Checked at bootstrap so
#: restarting the API after a live-demo run is the entire "make it live" step —
#: no separate reload endpoint, no hot-swap machinery to get right under time
#: pressure before a stage demo.
LIVE_DEMO_BLEND_PATH = "data/live_demo/blended_raw.parquet"


def _bootstrap_demo_store() -> IndexStore:
    """Build the in-memory demo store from deterministic synthetic data.

    Imported lazily: the synthetic collector pulls in numpy/pandas, and a production
    deployment that calls `configure_store` first should never touch it.

    A reference series is generated alongside the fares so `/validation/dgca`
    returns real content in the demo. It is synthetic and labelled as such — the
    report's own `data_mode_breakdown` says so on every response.
    """
    from pathlib import Path

    import pandas as pd

    from aipi.collectors.synthetic import default_demo_frame
    from aipi.weights import load_weights

    # 45 days, not the function's own 75-day default: this is the figure quoted
    # throughout docs/VALIDATION.md, README.md and docs/LIVE_DEMO_RUNBOOK.md as
    # "the seeded baseline". scripts/run_live_demo.py builds the identical frame
    # (same call) so its "before" state matches what a freshly booted API
    # actually serves, rather than a baseline that only existed in documentation.
    DEMO_BASELINE_DAYS = 45

    blend_path = Path(LIVE_DEMO_BLEND_PATH)
    is_live_demo_blend = blend_path.exists()
    if is_live_demo_blend:
        log.info("live-demo blend found at %s; booting from it", blend_path)
        raw = pd.read_parquet(blend_path)
    else:
        raw = default_demo_frame(n_days=DEMO_BASELINE_DAYS)
    weights = load_weights().weights

    # Build the reference from the cleaned fares the same way the seed script
    # does, so the demo exercises the full validation path rather than a stub.
    reference = None
    try:
        from aipi.cleaning import clean
        from scripts.seed_synthetic import build_dgca_reference

        reference = build_dgca_reference(clean(raw).index_input, seed=20260826)
    except Exception:  # noqa: BLE001 - the demo must still boot without a reference
        reference = None

    snapshot = build_snapshot(
        raw, route_weights=weights, reference=reference, enforce_slot=not is_live_demo_blend
    )
    return SnapshotStore(snapshot)


_last_blend_mtime: float | None = None


def get_store() -> IndexStore:
    """FastAPI dependency: the current store, bootstrapping the demo on first use.

    Normally a no-op lookup, because `main.lifespan` warms the store before the
    app accepts traffic. If new data lands in storage (e.g. from a live scraping run),
    it dynamically reloads and recomputes the econometric snapshot.
    """
    global _store, _last_blend_mtime
    from pathlib import Path

    blend_path = Path(LIVE_DEMO_BLEND_PATH)
    current_mtime = blend_path.stat().st_mtime if blend_path.exists() else None

    if _store is not None and current_mtime is not None and current_mtime != _last_blend_mtime:
        with _lock:
            if current_mtime != _last_blend_mtime:
                log.info("Detected new blended dataset in storage (mtime=%s); reloading store dynamically...", current_mtime)
                _store = _bootstrap_demo_store()
                _last_blend_mtime = current_mtime
                return _store

    if _store is None:
        with _lock:
            if _store is None:
                log.info("no store configured; building the demo snapshot (~11s)")
                _store = _bootstrap_demo_store()
                _last_blend_mtime = current_mtime
    return _store


def warm_store() -> None:
    """Build the store now, so the first real request does not pay for it.

    Called from the app lifespan. An 11-second first request is a bad first
    impression for someone whose entire onboarding is `docker compose up`, and it
    also makes the container report healthy before it can actually serve — the
    startup path is where that work belongs.
    """
    if is_configured():
        return
    get_store()
