"""The published validation report: backtest results plus honest lineage.

`aipi.validation.backtest` computes the statistics. This module assembles them
into the artefact a reader actually receives, and attaches the one field that
decides how much any of it is worth: **what fraction of the validated window was
real data**.

Why `data_mode_breakdown` is not optional
------------------------------------------
A back-test against a synthetic reference, run on synthetic fares, produces real
numbers — a Pearson r, a MAPE, a directional accuracy — that look exactly like a
validation. They are not one. They measure whether two simulations agree.

Publishing r = 0.82 without saying "100% synthetic" is the single most
misleading thing this project could do, and it would be an easy accident: the
number is computed by the same code either way. So the breakdown is computed
from the same rows the statistics were computed from, is required rather than
optional, and the plain-text summary leads with it rather than burying it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd

from aipi.validation.backtest import (
    BacktestResult,
    construct_validity_checks,
    national_backtest,
    pct_change,
    route_panel_backtest,
    to_monthly,
)


def data_mode_breakdown(df: pd.DataFrame) -> dict[str, float]:
    """Share of contributing rows by lineage. Sums to 1.0 over known modes."""
    if df.empty or "data_mode" not in df.columns:
        # Absent lineage is reported as fully unknown rather than assumed real —
        # an unlabelled pipeline is exactly the case this field exists to catch.
        return {"real": 0.0, "synthetic": 0.0, "unknown": 1.0}
    counts = df["data_mode"].astype(str).value_counts()
    total = float(counts.sum())
    out = {
        "real": float(counts.get("real", 0)) / total,
        "synthetic": float(counts.get("synthetic", 0)) / total,
    }
    known = out["real"] + out["synthetic"]
    out["unknown"] = max(0.0, 1.0 - known)
    return {k: round(v, 6) for k, v in out.items()}


@dataclass
class ValidationReport:
    """Everything published under /api/v1/validation/dgca."""

    generated_at: datetime
    #: period -> {aipi_index, dgca_index} for the overlay chart.
    series: list[dict[str, Any]]
    national: BacktestResult
    panel: BacktestResult
    construct_validity: dict[str, Any]
    data_mode: dict[str, float]
    reference_is_placeholder: bool
    notes: list[str] = field(default_factory=list)

    @property
    def is_fully_synthetic(self) -> bool:
        return self.data_mode.get("real", 0.0) <= 0.0

    def headline_caveat(self) -> str:
        """The sentence that must appear above any number in this report."""
        real = 100.0 * self.data_mode.get("real", 0.0)
        if real <= 0.0:
            return (
                "EVERY figure in this report is computed from SYNTHETIC fares "
                "validated against a SYNTHETIC reference. These statistics "
                "demonstrate that the validation pipeline works; they are not "
                "evidence that the index tracks real Indian airfares."
            )
        if real < 100.0:
            return (
                f"{real:.1f}% of the validated window is real collected data; the "
                f"remainder is synthetic back-fill. Statistics below are a blend "
                "and should not be read as a pure out-of-sample validation."
            )
        return (
            "Computed entirely from real collected fares. Reference data "
            + ("is PLACEHOLDER." if self.reference_is_placeholder else "is DGCA-sourced.")
        )

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "data_mode_breakdown": self.data_mode,
            "reference_is_placeholder": self.reference_is_placeholder,
            "caveat": self.headline_caveat(),
            "series": self.series,
            "pearson_r": self.panel.pearson_r,
            "mape": self.panel.mape_pct,
            "directional_accuracy": self.panel.directional_accuracy,
            "primary_comparison": "route_month_panel",
            "national_monthly": self.national.to_dict(),
            "route_month_panel": self.panel.to_dict(),
            "construct_validity": self.construct_validity,
            "notes": self.notes,
        }

    def to_text(self) -> str:
        lines = [
            "=" * 72,
            "AIPI VALIDATION REPORT",
            "=" * 72,
            "",
            self.headline_caveat(),
            "",
            f"generated                {self.generated_at.isoformat()}",
            f"data mode                real={self.data_mode['real']:.1%} "
            f"synthetic={self.data_mode['synthetic']:.1%}",
            f"reference                "
            f"{'PLACEHOLDER' if self.reference_is_placeholder else 'DGCA'}",
            "",
            "-- route-month panel (primary; has degrees of freedom) --",
            f"  n paired movements     {self.panel.n}",
        ]
        if self.panel.insufficient_n:
            lines.append("  statistics             NOT REPORTED (n below threshold)")
        else:
            lines += [
                f"  pearson r              {self.panel.pearson_r:.4f}",
                f"  spearman rho           {self.panel.spearman_rho:.4f}",
                f"  MAPE %                 {self.panel.mape_pct:.3f}",
                f"  directional accuracy   {self.panel.directional_accuracy:.1%}",
            ]
        lines += [
            "",
            "-- national monthly (under-powered on short windows) --",
            f"  n paired movements     {self.national.n}",
        ]
        if self.national.insufficient_n:
            lines.append("  statistics             NOT REPORTED (n below threshold)")
        else:
            lines.append(f"  pearson r              {self.national.pearson_r:.4f}")

        lines += ["", "-- construct validity --"]
        for k, v in self.construct_validity.items():
            lines.append(f"  {k:<32}{v}")

        if self.panel.notes:
            lines += ["", "-- notes --"]
            lines += [f"  * {n}" for n in self.panel.notes]
        return "\n".join(lines)


def _reference_to_route_monthly(
    reference: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    """(period, route_code, avg_fare) rows -> {route: {period: fare}}."""
    out: dict[str, dict[str, float]] = {}
    for row in reference.itertuples(index=False):
        out.setdefault(str(row.route_code), {})[str(row.period)] = float(row.avg_fare)
    return out


def _national_from_routes(
    route_monthly: Mapping[str, Mapping[str, float]],
    weights: Mapping[str, float],
) -> dict[str, float]:
    """Weighted national average fare per month, from the route reference."""
    periods: set[str] = set()
    for series in route_monthly.values():
        periods |= set(series)
    out: dict[str, float] = {}
    for period in sorted(periods):
        num = 0.0
        wsum = 0.0
        for route_code, series in route_monthly.items():
            fare = series.get(period)
            w = float(weights.get(route_code, 0.0))
            if fare is None or w <= 0:
                continue
            num += w * fare
            wsum += w
        if wsum > 0:
            out[period] = num / wsum
    return out


def build_validation_report(
    *,
    daily_index: Mapping[date, float],
    route_index: Mapping[str, Mapping[date, float]],
    reference: pd.DataFrame,
    route_weights: Mapping[str, float],
    contributing_rows: pd.DataFrame,
    leadtime_price_curve: Mapping[date, Mapping[int, float]] | None = None,
    min_days_per_month: int = 20,
) -> ValidationReport:
    """Assemble the full validation report from an index run and a reference."""
    route_monthly = _reference_to_route_monthly(reference)
    national_monthly = _national_from_routes(route_monthly, route_weights)

    national = national_backtest(
        daily_index, national_monthly, min_days_per_month=min_days_per_month
    )
    panel = route_panel_backtest(
        route_index, route_monthly, min_days_per_month=min_days_per_month
    )

    # Overlay series: AIPI monthly index vs the reference rebased to the same
    # base month, so the two are visually comparable without implying that a
    # level comparison is meaningful (it is not — see backtest module docstring).
    aipi_monthly = to_monthly(daily_index, min_days=min_days_per_month)
    ref_periods = sorted(set(aipi_monthly) & set(national_monthly))
    series: list[dict[str, Any]] = []
    if ref_periods:
        ref_base = national_monthly[ref_periods[0]]
        aipi_base = aipi_monthly[ref_periods[0]]
        for period in ref_periods:
            series.append(
                {
                    "period": period,
                    "aipi_index": round(
                        100.0 * aipi_monthly[period] / aipi_base, 4
                    ),
                    "dgca_index": round(
                        100.0 * national_monthly[period] / ref_base, 4
                    ),
                }
            )

    is_placeholder = True
    if "is_placeholder" in reference.columns and not reference.empty:
        is_placeholder = bool(reference["is_placeholder"].astype(bool).any())

    notes: list[str] = []
    if len(ref_periods) < 2:
        notes.append(
            f"Only {len(ref_periods)} complete month(s) overlap between the index "
            "and the reference. Month-on-month movement needs at least two, so the "
            "national comparison cannot be computed yet — this resolves itself as "
            "collection accumulates and is not a defect."
        )
    notes.append(
        "The overlay rebases both series to the first shared month so they can be "
        "plotted together. This is a MOVEMENT comparison; the level gap between an "
        "index and a rupee average fare carries no information."
    )

    return ValidationReport(
        generated_at=datetime.now(UTC),
        series=series,
        national=national,
        panel=panel,
        construct_validity=construct_validity_checks(
            daily_index, leadtime_price_curve=leadtime_price_curve
        ),
        data_mode=data_mode_breakdown(contributing_rows),
        reference_is_placeholder=is_placeholder,
        notes=notes,
    )


def write_report(report: ValidationReport, out_dir) -> None:
    """Persist both artefacts: JSON for machines, text for the submission."""
    from pathlib import Path

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "validation.json").write_text(
        json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8"
    )
    (out / "validation.txt").write_text(report.to_text(), encoding="utf-8")


__all__ = [
    "ValidationReport",
    "build_validation_report",
    "data_mode_breakdown",
    "pct_change",
    "write_report",
]
