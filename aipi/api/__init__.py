"""FastAPI service for AIPI.

The API's whole job is to publish index values *with the context that makes them
statistics* — sample size, coverage, base period, and the provenance of the run that
produced them. Endpoints are thin: they read from an `IndexStore` and shape the
response. All computation lives in the engine and the store, so the same handlers
serve the in-memory demo and the PostgreSQL deployment unchanged.
"""

from aipi.api.main import app, create_app

__all__ = ["app", "create_app"]
