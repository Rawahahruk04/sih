"""Tests for the elementary aggregate.

Expected values here are derived by hand in the docstrings, not captured from a
previous run. A test that only asserts "the code still does what it did" cannot
catch a formula that was wrong from the start.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from aipi.index.elementary import (
    chained_jevons,
    chained_jevons_with_gaps,
    geometric_mean,
    jevons_bilateral,
    log_jevons_bilateral,
    matched_items,
    matched_sample_sizes,
    naive_gm_level_index,
)

D = [date(2026, 8, d) for d in range(1, 12)]


class TestGeometricMean:
    def test_known_value(self):
        # GM(1, 4) = sqrt(4) = 2
        assert geometric_mean([1.0, 4.0]) == pytest.approx(2.0)

    def test_three_values(self):
        # GM(2, 4, 8) = (64)^(1/3) = 4
        assert geometric_mean([2.0, 4.0, 8.0]) == pytest.approx(4.0)

    def test_single_observation(self):
        assert geometric_mean([4567.0]) == pytest.approx(4567.0)

    def test_gm_is_at_most_arithmetic_mean(self):
        vals = [3200.0, 4100.0, 9800.0, 15600.0]
        assert geometric_mean(vals) < sum(vals) / len(vals)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            geometric_mean([])

    @pytest.mark.parametrize("bad", [[0.0, 100.0], [-50.0, 100.0]])
    def test_non_positive_raises_rather_than_dropping(self, bad):
        # A zero fare is a collection bug. Failing loudly is the point.
        with pytest.raises(ValueError, match="non-positive"):
            geometric_mean(bad)


class TestJevonsBilateral:
    def test_uniform_10pct_increase(self):
        s = {"6E-101": 5000.0, "6E-203": 8000.0}
        t = {"6E-101": 5500.0, "6E-203": 8800.0}
        assert jevons_bilateral(s, t) == pytest.approx(1.10)

    def test_no_change(self):
        s = {"a": 4000.0, "b": 9000.0}
        assert jevons_bilateral(s, s) == pytest.approx(1.0)

    def test_offsetting_moves_cancel_geometrically(self):
        # One fare doubles, the other halves: GM(2, 0.5) = 1 exactly.
        s = {"a": 4000.0, "b": 4000.0}
        t = {"a": 8000.0, "b": 2000.0}
        assert jevons_bilateral(s, t) == pytest.approx(1.0)

    def test_only_matched_items_are_used(self):
        # 'c' exists only at t and must be ignored entirely, however extreme.
        s = {"a": 5000.0, "b": 5000.0}
        t = {"a": 5500.0, "b": 5500.0, "c": 99_000.0}
        assert jevons_bilateral(s, t) == pytest.approx(1.10)
        assert matched_items(s, t) == ["a", "b"]

    def test_not_estimable_returns_none_not_one(self):
        # Distinguishing "cannot estimate" from "no change" is the whole point.
        s = {"a": 5000.0}
        t = {"b": 5000.0}
        assert jevons_bilateral(s, t, min_matched=1) is None

    def test_min_matched_threshold_enforced(self):
        s = {"a": 5000.0, "b": 6000.0}
        t = {"a": 5500.0}
        assert jevons_bilateral(s, t, min_matched=2) is None
        assert jevons_bilateral(s, t, min_matched=1) == pytest.approx(1.10)

    def test_log_form_agrees_with_level_form(self):
        s = {"a": 3300.0, "b": 7700.0, "c": 12_100.0}
        t = {"a": 3600.0, "b": 7100.0, "c": 14_000.0}
        assert math.exp(log_jevons_bilateral(s, t)) == pytest.approx(jevons_bilateral(s, t))

    def test_symmetry_in_logs(self):
        s = {"a": 4000.0, "b": 6000.0}
        t = {"a": 5000.0, "b": 6600.0}
        assert log_jevons_bilateral(s, t) == pytest.approx(-log_jevons_bilateral(t, s))

    def test_empty_inputs(self):
        assert jevons_bilateral({}, {}, min_matched=1) is None


class TestChainedJevons:
    def test_two_periods(self):
        panel = {D[0]: {"a": 5000.0, "b": 5000.0}, D[1]: {"a": 5500.0, "b": 5500.0}}
        s = chained_jevons(panel, min_matched=1)
        assert s[D[0]] == pytest.approx(100.0)
        assert s[D[1]] == pytest.approx(110.0)

    def test_links_compound(self):
        # +10% then +10% => 121, not 120.
        panel = {
            D[0]: {"a": 1000.0},
            D[1]: {"a": 1100.0},
            D[2]: {"a": 1210.0},
        }
        s = chained_jevons(panel, min_matched=1)
        assert s[D[2]] == pytest.approx(121.0)

    def test_unestimable_link_carries_forward_and_is_reported(self):
        panel = {
            D[0]: {"a": 1000.0},
            D[1]: {"b": 9999.0},  # no overlap with either neighbour
            D[2]: {"a": 1200.0},
        }
        series, gaps = chained_jevons_with_gaps(panel, min_matched=1)
        assert gaps == [D[1], D[2]]
        # Carried forward, NOT imputed from the unmatched item's price.
        assert series[D[1]] == pytest.approx(100.0)
        assert series[D[2]] == pytest.approx(100.0)

    def test_empty_panel(self):
        assert chained_jevons({}) == {}

    def test_single_period(self):
        assert chained_jevons({D[0]: {"a": 1000.0}}) == {D[0]: 100.0}


class TestCompositionBias:
    """The GM-of-levels index is not a Jevons index. This proves it."""

    def test_gm_of_levels_records_inflation_that_nobody_paid(self):
        # Two flights, NEITHER changes price. The cheap one stops operating.
        # A matched index must report no change. GM-of-levels reports +41%.
        panel = {
            D[0]: {"cheap": 3000.0, "dear": 6000.0},
            D[1]: {"dear": 6000.0},
        }
        matched = chained_jevons(panel, min_matched=1)
        naive = naive_gm_level_index(panel)

        assert matched[D[1]] == pytest.approx(100.0)  # correct: no price moved
        # GM(3000, 6000) = 4242.6 -> 6000 is +41.4%
        assert naive[D[1]] == pytest.approx(100.0 * 6000.0 / math.sqrt(3000.0 * 6000.0))
        assert naive[D[1]] > 141.0

    def test_the_two_agree_when_the_item_set_is_stable(self):
        panel = {
            D[0]: {"a": 4000.0, "b": 8000.0},
            D[1]: {"a": 4400.0, "b": 8800.0},
            D[2]: {"a": 4000.0, "b": 8000.0},
        }
        matched = chained_jevons(panel, min_matched=1)
        naive = naive_gm_level_index(panel)
        for d in panel:
            assert matched[d] == pytest.approx(naive[d])


class TestSampleSizes:
    def test_matched_n_is_the_effective_sample_size(self):
        panel = {
            D[0]: {"a": 1.0, "b": 1.0, "c": 1.0},
            D[1]: {"a": 1.0, "b": 1.0},  # c gone -> 2 matched, not 3 observed
            D[2]: {"a": 1.0, "b": 1.0, "d": 1.0},  # d is new -> still 2 matched
        }
        n = matched_sample_sizes(panel)
        assert n[D[0]] == 3
        assert n[D[1]] == 2
        assert n[D[2]] == 2
