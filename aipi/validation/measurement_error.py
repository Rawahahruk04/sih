"""Measurement-error simulation — what the current monthly process actually costs.

This is the analysis that answers "why should MoSPI care", with a number derived
from data rather than an argument.

The method is simple and hard to dispute:

  1. Take the daily index. Its monthly mean is the best available estimate of the
     true monthly average fare movement.
  2. Now sample it the way the existing process does — a small number of
     collection days per month.
  3. The gap between the sampled estimate and the monthly mean IS the measurement
     error the current process carries. Repeat over many random draws of which
     days get sampled, and the result is a distribution of that error.

Two statistics matter to a statistical office:

  * **MAE / p95 error** — how far off a monthly reading typically lands.
  * **Direction-error rate** — how often monthly sampling gets the *sign* of the
    month-on-month change wrong. A sub-index that reports the wrong direction is
    worse than a noisy one, because it is read as signal.

And one statistic matters to a policymaker: `required_sampling_days` — how many
collection days per month the current design would need to reach a target
accuracy. Daily collection reaches it by construction; this quantifies the
alternative.

Framing discipline: this bounds the error of *sampling a volatile series
sparsely*. It is a statement about sampling frequency, not an audit of MoSPI's
collection practice, and it must be presented that way.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date

import numpy as np

#: Fewer days than this in a month and that month is dropped: a partial month has
#: no defensible "true monthly average" to compare against.
MIN_DAYS_PER_MONTH = 20


@dataclass
class MeasurementErrorReport:
    days_per_month: int
    n_draws: int
    months: list[str]
    n_months: int

    bias_pct: float
    mae_pct: float
    rmse_pct: float
    p95_abs_pct: float
    max_abs_pct: float

    direction_error_rate: float
    n_direction_comparisons: int

    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "days_per_month": self.days_per_month,
            "n_draws": self.n_draws,
            "months": self.months,
            "n_months": self.n_months,
            "bias_pct": round(self.bias_pct, 4),
            "mae_pct": round(self.mae_pct, 4),
            "rmse_pct": round(self.rmse_pct, 4),
            "p95_abs_pct": round(self.p95_abs_pct, 4),
            "max_abs_pct": round(self.max_abs_pct, 4),
            "direction_error_rate": round(self.direction_error_rate, 4),
            "n_direction_comparisons": self.n_direction_comparisons,
            "notes": self.notes,
        }

    def headline_sentence(self) -> str:
        """The one line this whole module exists to produce."""
        return (
            f"Sampling {self.days_per_month} day(s) per month from the same fares "
            f"misses the true monthly average by {self.mae_pct:.2f}% on average "
            f"({self.p95_abs_pct:.2f}% at the 95th percentile), and reports the wrong "
            f"direction of month-on-month change {self.direction_error_rate * 100:.1f}% "
            f"of the time."
        )


def _group_by_month(daily: Mapping[date, float]) -> dict[str, list[float]]:
    months: dict[str, list[float]] = {}
    for d in sorted(daily):
        months.setdefault(f"{d.year:04d}-{d.month:02d}", []).append(float(daily[d]))
    return months


def simulate_monthly_sampling(
    daily: Mapping[date, float],
    *,
    days_per_month: int = 1,
    n_draws: int = 2000,
    seed: int = 20260826,
    min_days_per_month: int = MIN_DAYS_PER_MONTH,
) -> MeasurementErrorReport:
    """Quantify the error of estimating a monthly average from a sparse sample.

    Deterministic for a given ``seed`` — a published statistic must be
    reproducible bit for bit.
    """
    notes: list[str] = []
    by_month = _group_by_month(daily)

    usable = {m: v for m, v in by_month.items() if len(v) >= min_days_per_month}
    dropped = sorted(set(by_month) - set(usable))
    if dropped:
        notes.append(
            f"Partial months excluded (fewer than {min_days_per_month} days): {dropped}."
        )
    if not usable:
        raise ValueError(
            f"no month has {min_days_per_month}+ days; cannot establish a true monthly mean"
        )

    months = sorted(usable)
    rng = np.random.default_rng(seed)

    truth = np.array([np.mean(usable[m]) for m in months])  # (n_months,)

    # Draw `days_per_month` collection days per month, independently per draw.
    estimates = np.empty((n_draws, len(months)), dtype=float)
    for j, m in enumerate(months):
        vals = np.asarray(usable[m], dtype=float)
        k = min(days_per_month, len(vals))
        if k < days_per_month:
            notes.append(f"Month {m} has only {len(vals)} days; sampled {k}.")
        idx = np.array([rng.choice(len(vals), size=k, replace=False) for _ in range(n_draws)])
        estimates[:, j] = vals[idx].mean(axis=1)

    err_pct = 100.0 * (estimates - truth) / truth

    # Direction error: does the sampled month-on-month change have the right sign?
    direction_errors = 0
    comparisons = 0
    if len(months) >= 2:
        true_delta = np.diff(truth)
        est_delta = np.diff(estimates, axis=1)
        true_sign = np.sign(true_delta)
        est_sign = np.sign(est_delta)
        # Only count months where the truth actually moved — a flat month has no
        # direction to get wrong, and counting it would flatter the result.
        moved = true_sign != 0
        if moved.any():
            comparisons = int(n_draws * moved.sum())
            direction_errors = int((est_sign[:, moved] != true_sign[moved]).sum())

    return MeasurementErrorReport(
        days_per_month=days_per_month,
        n_draws=n_draws,
        months=months,
        n_months=len(months),
        bias_pct=float(err_pct.mean()),
        mae_pct=float(np.abs(err_pct).mean()),
        rmse_pct=float(np.sqrt((err_pct**2).mean())),
        p95_abs_pct=float(np.percentile(np.abs(err_pct), 95)),
        max_abs_pct=float(np.abs(err_pct).max()),
        direction_error_rate=(direction_errors / comparisons) if comparisons else 0.0,
        n_direction_comparisons=comparisons,
        notes=notes,
    )


def required_sampling_days(
    daily: Mapping[date, float],
    *,
    target_mae_pct: float = 1.0,
    max_days: int = 31,
    n_draws: int = 500,
    seed: int = 20260826,
) -> dict:
    """Smallest days-per-month whose MAE falls at or below ``target_mae_pct``.

    The policy-facing output: it converts "collect daily" from a preference into a
    cost comparison against the sampling effort the current design would need.
    """
    curve: list[dict[str, float]] = []
    answer: int | None = None
    for k in range(1, max_days + 1):
        try:
            rep = simulate_monthly_sampling(
                daily, days_per_month=k, n_draws=n_draws, seed=seed
            )
        except ValueError:
            break
        curve.append({"days_per_month": float(k), "mae_pct": round(rep.mae_pct, 4)})
        if answer is None and rep.mae_pct <= target_mae_pct:
            answer = k
            break
    return {
        "target_mae_pct": target_mae_pct,
        "required_days_per_month": answer,
        "achieved": answer is not None,
        "curve": curve,
    }


def sampling_error_curve(
    daily: Mapping[date, float],
    *,
    days: tuple[int, ...] = (1, 2, 3, 5, 7, 10, 15),
    n_draws: int = 500,
    seed: int = 20260826,
) -> list[dict]:
    """Error as a function of sampling intensity — the dashboard's evidence chart."""
    out = []
    for k in days:
        try:
            rep = simulate_monthly_sampling(daily, days_per_month=k, n_draws=n_draws, seed=seed)
        except ValueError:
            continue
        out.append(
            {
                "days_per_month": k,
                "mae_pct": round(rep.mae_pct, 4),
                "p95_abs_pct": round(rep.p95_abs_pct, 4),
                "direction_error_rate": round(rep.direction_error_rate, 4),
            }
        )
    return out
