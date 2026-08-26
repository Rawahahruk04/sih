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


def _bootstrap_demo_store() -> IndexStore:
    """Build the in-memory demo store from deterministic synthetic data.

    Imported lazily: the synthetic collector pulls in numpy/pandas, and a production
    deployment that calls `configure_store` first should never touch it.

    A reference series is generated alongside the fares so `/validation/dgca`
    returns real content in the demo. It is synthetic and labelled as such — the
    report's own `data_mode_breakdown` says so on every response.
    """
    from aipi.collectors.synthetic import default_demo_frame
    from aipi.weights import load_weights

    raw = default_demo_frame()
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

    snapshot = build_snapshot(raw, route_weights=weights, reference=reference)
    return SnapshotStore(snapshot)


def get_store() -> IndexStore:
    """FastAPI dependency: the current store, bootstrapping the demo on first use.

    Normally a no-op lookup, because `main.lifespan` warms the store before the
    app accepts traffic. The lazy path remains for callers that construct the app
    without running its lifespan (a bare `TestClient(app)` does not).
    """
    global _store
    if _store is None:
        with _lock:
            # Re-check inside the lock: another thread may have built it while
            # this one waited.
            if _store is None:
                log.info("no store configured; building the demo snapshot (~11s)")
                _store = _bootstrap_demo_store()
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
