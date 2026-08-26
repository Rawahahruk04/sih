"""Fare collectors. API-first; the scraper is a bounded, polite cross-check."""

from aipi.collectors.synthetic import (
    SyntheticConfig,
    default_demo_frame,
    demo_base_fares,
    demo_passengers,
    generate,
)

__all__ = [
    "SyntheticConfig",
    "default_demo_frame",
    "demo_base_fares",
    "demo_passengers",
    "generate",
]
