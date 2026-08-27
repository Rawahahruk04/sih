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
    _stats,
    construct_validity_checks,
    national_backtest,
    pct_change,
    route_panel_backtest,
    to_monthly,
)
from aipi.validation.cpi_reference import CpiReference


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
    #: Optional comparison against the real MoSPI CPI Transport series.
    #:
    #: Deliberately kept out of `data_mode` and `headline_caveat()`. Those two
    #: describe the lineage of the FARES being indexed; this describes the
    #: lineage of one thing they are compared against. A real reference does not
    #: make synthetic fares real, and conflating the two would let the report be
    #: quoted as "validated against real government data" when the underlying
    #: measurements are still simulated.
    secondary_reference: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def is_fully_synthetic(self) -> bool:
        """Whether the FARES are entirely synthetic. Independent of any reference."""
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
            "secondary_reference": self.secondary_reference,
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

        if self.secondary_reference:
            s = self.secondary_reference
            lines += [
                "",
                "-- secondary reference: MoSPI CPI Transport & Communication --",
                f"  reference is real      {not s['is_placeholder']}"
                f"   (base {s['base_year']})",
                f"  reference range        {s['reference_period_range'][0]}"
                f" .. {s['reference_period_range'][1]}"
                f"  ({s['reference_n_periods']} months)",
                f"  overlap with index     {s['overlap_months']} month(s)",
            ]
            if s["insufficient_n"]:
                lines.append(
                    "  statistics             NOT REPORTED "
                    f"(n={s['n_paired_movements']} paired movements)"
                )
            else:
                lines += [
                    f"  pearson r              {s['pearson_r']}",
                    f"  MAPE %                 {s['mape']}",
                    f"  directional accuracy   {s['directional_accuracy']}",
                ]
            if not s["is_placeholder"]:
                lines.append(
                    "  NOTE: this reference being real does NOT make the fares real "
                    "— see data mode above."
                )

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


def build_secondary_reference_block(
    aipi_monthly: Mapping[str, float],
    cpi: CpiReference,
) -> dict[str, Any]:
    """Compare the AIPI monthly series against the real MoSPI CPI Transport index.

    Reuses `national_backtest`'s statistics via the same `pct_change` +
    month-on-month machinery the DGCA comparison uses — the estimator is not
    duplicated, so a fix to one is a fix to both.

    Two caveats are attached to the output rather than left for a reader to
    infer, because both would otherwise make this block look stronger than it is:

    **Different estimands.** MoSPI's "Transport and Communication" sub-group
    covers petrol, diesel, bus and rail fares, and telephone charges. Airfare is
    a small component of it. Even a perfect airfare index should NOT track this
    series closely, so agreement is weak evidence and disagreement is not a
    defect. It is a sanity check on direction, not a validation of level.

    **Base periods differ.** CPI is 2012=100; AIPI's base is its own collection
    window. Only month-on-month *movements* are ever compared, never levels.
    """
    overlap = sorted(set(aipi_monthly) & set(cpi.series))
    aipi_chg = pct_change({p: aipi_monthly[p] for p in overlap})
    cpi_chg = pct_change({p: cpi.series[p] for p in overlap})
    paired = sorted(set(aipi_chg) & set(cpi_chg))

    x = [aipi_chg[p] for p in paired]
    y = [cpi_chg[p] for p in paired]
    pearson, spearman, mape, directional, insufficient, stat_notes = _stats(
        x, y, "cpi_transport_monthly"
    )

    notes = list(stat_notes)
    if not overlap:
        notes.append(
            f"NO TEMPORAL OVERLAP: the CPI reference ends {cpi.last_period} while "
            f"the index covers "
            f"{min(aipi_monthly) if aipi_monthly else 'nothing'}"
            f"..{max(aipi_monthly) if aipi_monthly else 'nothing'}. "
            "No statistic can be computed until collection reaches a month MoSPI "
            "has published, or the reference is refreshed. Reporting a correlation "
            "here would require inventing paired observations."
        )
    notes.append(
        "MoSPI's Transport & Communication sub-group covers fuel, bus, rail and "
        "telecom as well as air travel. Airfare is a small component, so this is a "
        "directional sanity check against a real published series — NOT a "
        "like-for-like validation of the airfare index."
    )
    notes.append(
        f"Base periods differ (CPI {cpi.base_year}; AIPI base = its own collection "
        "window), so only month-on-month movements are compared, never levels."
    )

    return {
        "source": "mospi_cpi_transport",
        "base_year": cpi.base_year,
        "is_placeholder": cpi.is_placeholder,
        "source_note": cpi.source_note,
        "reference_period_range": [cpi.first_period, cpi.last_period],
        "reference_n_periods": len(cpi.series),
        "reference_gaps": cpi.gaps,
        "overlap_months": len(overlap),
        "n_paired_movements": len(paired),
        "series": [
            {
                "period": p,
                "aipi_index": round(float(aipi_monthly[p]), 4),
                "cpi_transport_index": round(float(cpi.series[p]), 4),
            }
            for p in overlap
        ],
        "pearson_r": None if pearson is None else round(pearson, 4),
        "mape": None if mape is None else round(mape, 4),
        "directional_accuracy": (
            None if directional is None else round(directional, 4)
        ),
        "spearman_rho": None if spearman is None else round(spearman, 4),
        "insufficient_n": insufficient,
        "notes": notes,
    }


def build_validation_report(
    *,
    daily_index: Mapping[date, float],
    route_index: Mapping[str, Mapping[date, float]],
    reference: pd.DataFrame,
    route_weights: Mapping[str, float],
    contributing_rows: pd.DataFrame,
    leadtime_price_curve: Mapping[date, Mapping[int, float]] | None = None,
    min_days_per_month: int = 20,
    cpi_reference: CpiReference | None = None,
) -> ValidationReport:
    """Assemble the full validation report from an index run and its references.

    `cpi_reference` is the optional **real** MoSPI CPI Transport series. It is a
    secondary comparison and deliberately does NOT influence `data_mode` or
    `headline_caveat()` — see `ValidationReport` on why those two facts are
    independent.
    """
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

    secondary: dict[str, Any] | None = None
    if cpi_reference is not None:
        secondary = build_secondary_reference_block(aipi_monthly, cpi_reference)
        if not cpi_reference.is_placeholder:
            # The single most likely misreading of this report: "one reference is
            # real, therefore the validation is real." State the separation where
            # a reader cannot miss it.
            notes.append(
                "SCOPE OF THE 'REAL' LABEL: secondary_reference.is_placeholder is "
                "false because the MoSPI CPI Transport series is genuine published "
                "government data. That says nothing about the FARES being indexed, "
                "whose lineage is reported separately in data_mode_breakdown. A "
                "real reference compared against synthetic fares is still a "
                "synthetic result — the two facts are independent and both are "
                "published here deliberately."
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
        secondary_reference=secondary,
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
