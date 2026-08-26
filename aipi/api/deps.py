"""Store wiring for the API.

The store is a process-level singleton, resolved lazily. Tests and the production
entrypoint override it with `configure_store(...)`; if nothing overrides it, the API
bootstraps the zero-dependency demo store from synthetic data, so a bare `uvicorn
aipi.api:app` comes up with a working index and needs no database.
"""

from __future__ import annotations

from aipi.store import IndexStore, SnapshotStore, build_snapshot

_store: IndexStore | None = None


def configure_store(store: IndexStore) -> None:
    """Install the store the API should read from (production wiring, or a test)."""
    global _store
    _store = store


def _bootstrap_demo_store() -> IndexStore:
    """Build the in-memory demo store from deterministic synthetic data.

    Imported lazily: the synthetic collector pulls in numpy/pandas, and a production
    deployment that calls `configure_store` first should never touch it.
    """
    from aipi.collectors.synthetic import (
        default_demo_frame,
        demo_base_fares,
        demo_passengers,
    )
    from aipi.index.aggregate import expenditure_weights

    raw = default_demo_frame()
    weights = expenditure_weights(demo_passengers(), demo_base_fares())
    snapshot = build_snapshot(raw, route_weights=weights)
    return SnapshotStore(snapshot)


def get_store() -> IndexStore:
    """FastAPI dependency: the current store, bootstrapping the demo on first use."""
    global _store
    if _store is None:
        _store = _bootstrap_demo_store()
    return _store
