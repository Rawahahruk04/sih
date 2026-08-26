"""Load route weights from a DGCA traffic file.

Weights are the one input a price index cannot derive from its own data. They
come from outside — DGCA city-pair passenger volumes and base-period average
fares — so this module is the seam where an external, possibly-placeholder file
enters the system.

Two invariants it enforces, because both failure modes are silent:

  * **Weights must sum to 1** within a base period, or the headline is not an
    average of anything. Checked, not assumed.
  * **Placeholder provenance travels with the number.** A file marked
    `is_placeholder` produces weights marked `is_placeholder`, which the API
    surfaces. Illustrative figures that lose their label become "the weights"
    by the time anyone presents them, and nobody can tell afterwards.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from aipi.index.aggregate import expenditure_weights, quantity_weights

DEFAULT_WEIGHTS_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "reference"
    / "dgca_route_traffic_PLACEHOLDER.json"
)


class WeightsError(ValueError):
    """The weights file is unusable. Never fall back to uniform silently."""


@dataclass(frozen=True)
class WeightSet:
    """Base-period weights plus the provenance needed to publish them."""

    base_period: str
    #: route_code -> expenditure share (p0*q0 normalised). The Laspeyres weights.
    weights: dict[str, float]
    #: route_code -> passenger share. Retained to quantify the specification gap.
    quantity_shares: dict[str, float]
    passengers: dict[str, float]
    base_avg_fare: dict[str, float]
    is_placeholder: bool
    source_note: str

    def to_dict(self) -> dict:
        return {
            "base_period": self.base_period,
            "is_placeholder": self.is_placeholder,
            "source_note": self.source_note,
            "n_routes": len(self.weights),
            "weights": {k: round(v, 6) for k, v in sorted(self.weights.items())},
        }


def load_weights(path: Path | str | None = None) -> WeightSet:
    """Read a DGCA traffic file and derive expenditure weights from it."""
    path = Path(path) if path is not None else DEFAULT_WEIGHTS_FILE
    if not path.exists():
        raise WeightsError(
            f"weights file not found: {path}. Weights cannot be defaulted — an "
            "index with invented weights measures nothing in particular."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("routes") or []
    if not rows:
        raise WeightsError(f"{path} contains no route rows")

    passengers: dict[str, float] = {}
    base_avg_fare: dict[str, float] = {}
    for row in rows:
        code = str(row["route_code"])
        pax = float(row["passengers"])
        fare = float(row["base_avg_fare"])
        if pax <= 0 or fare <= 0:
            raise WeightsError(
                f"{path}: route {code} has non-positive passengers or fare "
                f"({pax}, {fare}). A zero-weight route should be removed from the "
                "basket explicitly, not encoded as a zero."
            )
        passengers[code] = pax
        base_avg_fare[code] = fare

    weights = expenditure_weights(passengers, base_avg_fare)
    total = sum(weights.values())
    if abs(total - 1.0) > 1e-9:
        raise WeightsError(f"weights sum to {total!r}, not 1.0")

    is_placeholder = bool(payload.get("is_placeholder", True))
    note = str(payload.get("_source_when_real", "")) if is_placeholder else ""
    return WeightSet(
        base_period=str(payload.get("base_period", "unknown")),
        weights=weights,
        quantity_shares=quantity_weights(passengers),
        passengers=passengers,
        base_avg_fare=base_avg_fare,
        is_placeholder=is_placeholder,
        source_note=(
            "PLACEHOLDER figures — not sourced from DGCA. " + note
            if is_placeholder
            else "Loaded from DGCA traffic data."
        ),
    )
