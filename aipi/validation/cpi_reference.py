"""MoSPI CPI Transport & Communication reference loader.

This is the one **real** external series in the project: the All-India CPI
Transport and Communication sub-group index (Rural+Urban combined, base
2012=100), published by MoSPI. Everything else the validation module compares
against is currently synthetic.

Provenance travels with the numbers, mirroring `aipi.weights.WeightSet`: a
caller can always ask "is this real, and where did it come from" without leaving
the object. `is_placeholder` is read from the file rather than assumed, because
the whole point of the flag is that it survives being copied around.

Gaps are data, not errors
--------------------------
The series is NOT a complete monthly grid. April and May 2020 are absent because
COVID lockdown suspended field price collection, and April 2019 is absent too.
Those months have no value — not zero, not the previous month carried forward.
Interpolating them would fabricate observations MoSPI never made, and would do it
precisely where the underlying prices moved most violently. So the loader keeps
gaps as gaps and reports them.

A row that cannot be parsed is skipped with its reason recorded, mirroring the
quarantine-reason discipline in `aipi.cleaning.contract`: one malformed row must
not cost the other 151, but the loss must be visible rather than silent.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_CPI_FILE = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "reference"
    / "mospi_cpi_transport_reference.json"
)

#: YYYY-MM, with the month constrained to 01-12 so "2025-13" is rejected rather
#: than silently sorting after December.
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

VALUE_FIELD = "transport_communication_index"


class CpiReferenceError(ValueError):
    """The reference file is unusable as a whole (missing, malformed, empty)."""


@dataclass
class CpiReference:
    """The MoSPI CPI Transport series plus the provenance needed to publish it."""

    #: period 'YYYY-MM' -> Transport & Communication sub-group index.
    series: dict[str, float]
    base_year: str
    is_placeholder: bool
    source_note: str
    series_used: str = ""
    retrieved: str = ""
    #: Rows dropped during load, as 'period: reason'. Empty on a clean file.
    skipped: list[str] = field(default_factory=list)
    #: Months absent between first and last observation. Genuine gaps, not errors.
    gaps: list[str] = field(default_factory=list)

    @property
    def periods(self) -> list[str]:
        return sorted(self.series)

    @property
    def first_period(self) -> str | None:
        return self.periods[0] if self.series else None

    @property
    def last_period(self) -> str | None:
        return self.periods[-1] if self.series else None

    def to_dict(self) -> dict:
        return {
            "base_year": self.base_year,
            "is_placeholder": self.is_placeholder,
            "source_note": self.source_note,
            "series_used": self.series_used,
            "retrieved": self.retrieved,
            "n_periods": len(self.series),
            "first_period": self.first_period,
            "last_period": self.last_period,
            "gaps": self.gaps,
            "skipped": self.skipped,
        }


def _expected_month_grid(first: str, last: str) -> list[str]:
    y0, m0 = (int(x) for x in first.split("-"))
    y1, m1 = (int(x) for x in last.split("-"))
    out: list[str] = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m, y = 1, y + 1
    return out


def load_cpi_reference(path: Path | str | None = None) -> CpiReference:
    """Read the MoSPI CPI Transport file into a `CpiReference`.

    Raises `CpiReferenceError` only for whole-file problems. Individual bad rows
    are skipped and recorded on `CpiReference.skipped`.
    """
    path = Path(path) if path is not None else DEFAULT_CPI_FILE
    if not path.exists():
        raise CpiReferenceError(
            f"CPI reference not found: {path}. This is the project's only real "
            "external series; it is not something to default or fabricate."
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CpiReferenceError(f"{path} is not valid JSON: {exc}") from exc

    rows = payload.get("series")
    if not isinstance(rows, list) or not rows:
        raise CpiReferenceError(f"{path} has no 'series' array")

    series: dict[str, float] = {}
    skipped: list[str] = []

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            skipped.append(f"row {i}: not an object")
            continue

        period = str(row.get("period", "")).strip()
        if not PERIOD_RE.match(period):
            skipped.append(f"row {i}: period {period!r} is not YYYY-MM")
            continue
        if period in series:
            # A duplicate period would silently overwrite, changing the series
            # depending on file order. Refuse the second one and say so.
            skipped.append(f"{period}: duplicate period, second occurrence ignored")
            continue

        raw_value = row.get(VALUE_FIELD)
        if raw_value is None:
            # A genuinely absent value (an NA cell) is a gap, not a defect.
            skipped.append(f"{period}: {VALUE_FIELD} absent")
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            skipped.append(f"{period}: {VALUE_FIELD}={raw_value!r} is not numeric")
            continue
        if value <= 0:
            skipped.append(f"{period}: {VALUE_FIELD}={value} is not a positive index")
            continue

        series[period] = value

    if not series:
        raise CpiReferenceError(
            f"{path} yielded no usable periods. Skipped: {skipped[:5]}"
        )

    ordered = sorted(series)
    gaps = [p for p in _expected_month_grid(ordered[0], ordered[-1]) if p not in series]

    if skipped:
        log.warning("CPI reference: skipped %d row(s): %s", len(skipped), skipped[:5])
    if gaps:
        log.info(
            "CPI reference has %d gap month(s) (%s) — retained as gaps, never "
            "interpolated",
            len(gaps), ", ".join(gaps),
        )

    is_placeholder = bool(payload.get("_is_placeholder", True))
    source_note = " | ".join(
        str(payload.get(k, "")).strip()
        for k in ("_source", "_source_dataset_name", "_source_portal")
        if str(payload.get(k, "")).strip()
    )

    return CpiReference(
        series=series,
        base_year=str(payload.get("_base_year", "unknown")),
        is_placeholder=is_placeholder,
        source_note=source_note or "source not recorded in file",
        series_used=str(payload.get("_series_used", "")),
        retrieved=str(payload.get("_retrieved", "")),
        skipped=skipped,
        gaps=gaps,
    )
