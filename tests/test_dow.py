"""Tests for day-of-week adjustment.

The recovery test is exact, not approximate: a centred 7-day window spans each
weekday exactly once, so a multiplicative weekly pattern imposed on a smooth
trend must be recovered to machine precision. If the estimator cannot do that on
synthetic data whose true factors are known, it cannot be trusted on real data.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from aipi.index.dow import (
    IDENTITY_FACTORS,
    MIN_DAYS_FOR_DOW,
    adjust_series,
    centred_log_ma,
    dow_amplitude_pct,
    estimate_dow_factors,
)

START = date(2026, 6, 1)  # a Monday

#: Friday/Sunday dear, Tuesday/Wednesday cheap — the real Indian pattern's shape.
#: Normalised so the product over the week is exactly 1.
_RAW = {0: 0.98, 1: 0.94, 2: 0.95, 3: 1.02, 4: 1.09, 5: 1.00, 6: 1.06}
_GEO = math.exp(sum(math.log(v) for v in _RAW.values()) / 7)
TRUE_FACTORS = {d: v / _GEO for d, v in _RAW.items()}


def synthetic_series(n_days: int, daily_drift: float = 0.001) -> dict[date, float]:
    """Smooth exponential trend times a fixed weekly pattern."""
    out = {}
    for i in range(n_days):
        d = START + timedelta(days=i)
        out[d] = 100.0 * math.exp(daily_drift * i) * TRUE_FACTORS[d.weekday()]
    return out


class TestFactorRecovery:
    def test_recovers_known_factors_to_machine_precision(self):
        est = estimate_dow_factors(synthetic_series(35))
        for dow, truth in TRUE_FACTORS.items():
            assert est[dow] == pytest.approx(truth, abs=1e-12)

    def test_factors_multiply_to_one(self):
        est = estimate_dow_factors(synthetic_series(35))
        product = math.prod(est.values())
        assert product == pytest.approx(1.0)

    def test_adjustment_removes_the_weekly_cycle(self):
        series = synthetic_series(35)
        adj = adjust_series(series, estimate_dow_factors(series))
        # What remains must be the pure trend: every successive ratio identical.
        days = sorted(adj)
        ratios = [adj[b] / adj[a] for a, b in zip(days, days[1:], strict=False)]
        assert max(ratios) == pytest.approx(min(ratios), abs=1e-9)
        assert ratios[0] == pytest.approx(math.exp(0.001))

    def test_adjustment_does_not_move_the_level(self):
        """Factors multiplying to 1 means the geometric mean is untouched."""
        series = synthetic_series(35)
        adj = adjust_series(series, estimate_dow_factors(series))
        # Compare over whole weeks so each weekday appears equally often.
        days = sorted(series)[:35]
        gm_raw = math.exp(sum(math.log(series[d]) for d in days) / len(days))
        gm_adj = math.exp(sum(math.log(adj[d]) for d in days) / len(days))
        assert gm_adj == pytest.approx(gm_raw)

    def test_flat_series_yields_unit_factors(self):
        flat = {START + timedelta(days=i): 100.0 for i in range(35)}
        est = estimate_dow_factors(flat)
        for dow in range(7):
            assert est[dow] == pytest.approx(1.0)


class TestGuards:
    def test_short_series_degrades_to_identity(self):
        assert estimate_dow_factors(synthetic_series(MIN_DAYS_FOR_DOW - 1)) == IDENTITY_FACTORS

    def test_gappy_series_degrades_to_identity_rather_than_fitting_noise(self):
        series = synthetic_series(35)
        # Remove every Sunday: that weekday can no longer be identified.
        for d in list(series):
            if d.weekday() == 6:
                del series[d]
        assert estimate_dow_factors(series) == IDENTITY_FACTORS

    def test_identity_factors_leave_series_untouched(self):
        series = synthetic_series(10)
        assert adjust_series(series, IDENTITY_FACTORS) == pytest.approx(series)

    def test_empty_series(self):
        assert estimate_dow_factors({}) == IDENTITY_FACTORS


class TestCentredMovingAverage:
    def test_only_full_windows_are_returned(self):
        series = {START + timedelta(days=i): 100.0 for i in range(9)}
        ma = centred_log_ma(series, window=7)
        # 9 days, window 7 -> only days 3..5 (0-indexed) have a full span.
        assert sorted(ma) == [START + timedelta(days=i) for i in (3, 4, 5)]

    def test_constant_series_ma_equals_log_level(self):
        series = {START + timedelta(days=i): 250.0 for i in range(9)}
        ma = centred_log_ma(series)
        for v in ma.values():
            assert v == pytest.approx(math.log(250.0))


class TestAmplitude:
    def test_amplitude_reports_peak_to_trough_spread(self):
        est = estimate_dow_factors(synthetic_series(35))
        # True spread: 1.09 / 0.94 - 1 = 15.96%
        assert dow_amplitude_pct(est) == pytest.approx(100.0 * (1.09 / 0.94 - 1.0), abs=1e-6)

    def test_flat_factors_have_zero_amplitude(self):
        assert dow_amplitude_pct(IDENTITY_FACTORS) == pytest.approx(0.0)
