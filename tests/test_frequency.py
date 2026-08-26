"""Weekly/monthly resampling: hand-computed expectations.

The load-bearing property is that a period index is a CHAINED construction, not
an average of index levels. These tests pin the difference with numbers derived
by hand rather than by running the code and blessing its output.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from aipi.index.frequency import (
    incomplete_months,
    month_start,
    to_monthly,
    to_weekly,
    week_start,
)


def test_week_start_is_monday() -> None:
    # 2026-08-26 is a Wednesday; its ISO week starts Monday 2026-08-24.
    assert week_start(date(2026, 8, 26)) == date(2026, 8, 24)
    assert week_start(date(2026, 8, 24)) == date(2026, 8, 24)
    # Sunday belongs to the week that started the previous Monday.
    assert week_start(date(2026, 8, 30)) == date(2026, 8, 24)


def test_month_start() -> None:
    assert month_start(date(2026, 8, 26)) == date(2026, 8, 1)


def test_monthly_is_geometric_mean_of_daily_levels() -> None:
    """Hand-computed: GM of 100, 110, 121 is exactly 110."""
    daily = {
        date(2026, 6, 1): 100.0,
        date(2026, 6, 2): 110.0,
        date(2026, 6, 3): 121.0,
    }
    result = to_monthly(daily)
    assert result.series[date(2026, 6, 1)] == pytest.approx(110.0, abs=1e-9)


def test_geometric_and_arithmetic_means_differ_on_volatile_input() -> None:
    """The whole reason for chaining: on a volatile series the two diverge.

    GM(50, 200) = 100 exactly. AM(50, 200) = 125. A monthly index built by
    averaging levels would report +25% inflation that nobody experienced, because
    the series ended exactly where a compounding reading says it did.
    """
    daily = {date(2026, 6, 1): 50.0, date(2026, 6, 2): 200.0}
    result = to_monthly(daily)
    assert result.series[date(2026, 6, 1)] == pytest.approx(100.0, abs=1e-9)
    assert result.mean_of_levels[date(2026, 6, 1)] == pytest.approx(125.0, abs=1e-9)
    assert result.mean_abs_gap == pytest.approx(25.0, abs=1e-9)


def test_period_ratio_equals_geometric_mean_of_daily_ratios() -> None:
    """Transitivity: the property that makes the chained construction correct.

    If every day in July is exactly 1.10x its June counterpart, the monthly
    index must move by exactly 10% — regardless of how volatile the level was
    within each month.
    """
    june = {date(2026, 6, d): v for d, v in [(1, 100.0), (2, 130.0), (3, 90.0)]}
    july = {date(2026, 7, d): v * 1.10 for d, v in [(1, 100.0), (2, 130.0), (3, 90.0)]}
    result = to_monthly({**june, **july})
    ratio = result.series[date(2026, 7, 1)] / result.series[date(2026, 6, 1)]
    assert ratio == pytest.approx(1.10, abs=1e-12)


def test_uniform_inflation_is_reproduced_exactly() -> None:
    daily = {date(2026, 6, 1 + i): 100.0 * (1.01**i) for i in range(28)}
    result = to_monthly(daily)
    expected = math.exp(sum(math.log(v) for v in daily.values()) / len(daily))
    assert result.series[date(2026, 6, 1)] == pytest.approx(expected, abs=1e-9)


def test_period_on_period_pct() -> None:
    daily = {
        date(2026, 6, 1): 100.0,
        date(2026, 7, 1): 110.0,
    }
    result = to_monthly(daily)
    pop = result.period_on_period_pct()
    assert pop[date(2026, 7, 1)] == pytest.approx(10.0, abs=1e-9)


def test_weekly_buckets_by_iso_week() -> None:
    from datetime import timedelta

    start = date(2026, 8, 24)  # a Monday
    daily = {start + timedelta(days=i): 100.0 for i in range(14)}
    result = to_weekly(daily)
    assert sorted(result.series) == [date(2026, 8, 24), date(2026, 8, 31)]
    assert result.n_days[date(2026, 8, 24)] == 7
    assert result.n_days[date(2026, 8, 31)] == 7


def test_incomplete_months_are_identified() -> None:
    """A 5-day month must be flagged, not silently published beside a full one."""
    daily = {date(2026, 6, 1 + i): 100.0 for i in range(28)}
    daily.update({date(2026, 7, 1 + i): 100.0 for i in range(5)})
    partial = incomplete_months(daily)
    assert date(2026, 7, 1) in partial
    assert date(2026, 6, 1) not in partial


def test_empty_input_does_not_raise() -> None:
    assert to_monthly({}).series == {}
    assert to_weekly({}).series == {}


def test_non_positive_levels_are_skipped_not_logged() -> None:
    """A zero index level is a bug upstream; it must not produce log(0) = -inf."""
    daily = {date(2026, 6, 1): 100.0, date(2026, 6, 2): 0.0}
    result = to_monthly(daily)
    assert math.isfinite(result.series[date(2026, 6, 1)])
    assert result.series[date(2026, 6, 1)] == pytest.approx(100.0, abs=1e-9)
