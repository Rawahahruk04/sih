"""Tests for upper-level aggregation, weighting, and base-period handling.

`TestWeightSpecification` is the test that encodes the most consequential
methodological correction in this project: Laspeyres weights are base-period
EXPENDITURE shares, not passenger-volume shares.
"""

from __future__ import annotations

from datetime import date

import pytest

from aipi.index.aggregate import (
    expenditure_weights,
    headline_coverage,
    laspeyres_headline,
    quantity_weights,
    rebase_to_period_mean,
    select_base_periods,
    uniform_booking_weights,
    weight_divergence,
    window_aggregate,
)

D = [date(2026, 8, d) for d in range(1, 32)]


class TestWeightSpecification:
    """Two routes carry identical passenger counts; one costs 3x as much."""

    PASSENGERS = {"DEL-BOM": 100_000.0, "DEL-GAU": 100_000.0}
    BASE_FARE = {"DEL-BOM": 5_000.0, "DEL-GAU": 15_000.0}

    def test_expenditure_weights_are_fare_weighted(self):
        # Expenditure: 5e8 and 1.5e9 -> shares 0.25 / 0.75
        w = expenditure_weights(self.PASSENGERS, self.BASE_FARE)
        assert w["DEL-BOM"] == pytest.approx(0.25)
        assert w["DEL-GAU"] == pytest.approx(0.75)

    def test_quantity_weights_ignore_fare_level(self):
        w = quantity_weights(self.PASSENGERS)
        assert w["DEL-BOM"] == pytest.approx(0.5)
        assert w["DEL-GAU"] == pytest.approx(0.5)

    def test_weights_sum_to_one(self):
        assert sum(expenditure_weights(self.PASSENGERS, self.BASE_FARE).values()) == pytest.approx(
            1.0
        )
        assert sum(quantity_weights(self.PASSENGERS).values()) == pytest.approx(1.0)

    def test_the_two_specifications_give_materially_different_headlines(self):
        """Quantifies the error: 25 index points on this sample."""
        routes = {"DEL-BOM": {D[0]: 100.0}, "DEL-GAU": {D[0]: 200.0}}
        correct = laspeyres_headline(routes, expenditure_weights(self.PASSENGERS, self.BASE_FARE))
        wrong = laspeyres_headline(routes, quantity_weights(self.PASSENGERS))
        assert correct[D[0]] == pytest.approx(175.0)  # 0.25*100 + 0.75*200
        assert wrong[D[0]] == pytest.approx(150.0)  # 0.50*100 + 0.50*200
        assert abs(correct[D[0]] - wrong[D[0]]) == pytest.approx(25.0)

    def test_divergence_reported_in_basis_points(self):
        div = weight_divergence(
            expenditure_weights(self.PASSENGERS, self.BASE_FARE),
            quantity_weights(self.PASSENGERS),
        )
        assert div["DEL-BOM"] == pytest.approx(-2500.0)
        assert div["DEL-GAU"] == pytest.approx(2500.0)

    def test_zero_total_rejected(self):
        with pytest.raises(ValueError, match="sum to zero"):
            quantity_weights({"A": 0.0})

    def test_disjoint_inputs_rejected(self):
        with pytest.raises(ValueError, match="no routes common"):
            expenditure_weights({"A": 1.0}, {"B": 1.0})


class TestWindowAggregate:
    def test_uniform_weights_average_cell_indices(self):
        cells = {("DEL-BOM", 7): {D[0]: 100.0}, ("DEL-BOM", 14): {D[0]: 120.0}}
        out = window_aggregate(cells, uniform_booking_weights([7, 14]))
        assert out["DEL-BOM"][D[0]] == pytest.approx(110.0)

    def test_non_uniform_weights(self):
        cells = {("DEL-BOM", 7): {D[0]: 100.0}, ("DEL-BOM", 14): {D[0]: 200.0}}
        out = window_aggregate(cells, {7: 0.75, 14: 0.25})
        assert out["DEL-BOM"][D[0]] == pytest.approx(125.0)

    def test_missing_window_renormalises_instead_of_dragging_to_zero(self):
        cells = {
            ("DEL-BOM", 7): {D[0]: 100.0, D[1]: 150.0},
            ("DEL-BOM", 14): {D[0]: 120.0},  # absent on D[1]
        }
        out = window_aggregate(cells, uniform_booking_weights([7, 14]))
        assert out["DEL-BOM"][D[0]] == pytest.approx(110.0)
        assert out["DEL-BOM"][D[1]] == pytest.approx(150.0)  # not 75.0

    def test_zero_weight_window_excluded(self):
        cells = {("DEL-BOM", 7): {D[0]: 100.0}, ("DEL-BOM", 60): {D[0]: 999.0}}
        out = window_aggregate(cells, {7: 1.0, 60: 0.0})
        assert out["DEL-BOM"][D[0]] == pytest.approx(100.0)

    def test_routes_kept_separate(self):
        cells = {("DEL-BOM", 7): {D[0]: 100.0}, ("DEL-BLR", 7): {D[0]: 200.0}}
        out = window_aggregate(cells, {7: 1.0})
        assert out["DEL-BOM"][D[0]] == pytest.approx(100.0)
        assert out["DEL-BLR"][D[0]] == pytest.approx(200.0)


class TestLaspeyresHeadline:
    WEIGHTS = {"A": 0.6, "B": 0.3, "C": 0.1}

    def test_weighted_average(self):
        routes = {
            "A": {D[0]: 100.0},
            "B": {D[0]: 110.0},
            "C": {D[0]: 200.0},
        }
        # 0.6*100 + 0.3*110 + 0.1*200 = 60 + 33 + 20 = 113
        assert laspeyres_headline(routes, self.WEIGHTS)[D[0]] == pytest.approx(113.0)

    def test_missing_route_renormalises_over_present_weight(self):
        routes = {"A": {D[0]: 100.0}, "B": {D[0]: 110.0}}  # C absent
        # (0.6*100 + 0.3*110) / 0.9 = 93/0.9 = 103.333...
        assert laspeyres_headline(routes, self.WEIGHTS)[D[0]] == pytest.approx(103.3333, abs=1e-4)

    def test_coverage_is_weight_based_not_count_based(self):
        routes = {"A": {D[0]: 100.0}}  # 1 of 3 routes, but 60% of weight
        cov = headline_coverage(routes, self.WEIGHTS)
        assert cov[D[0]] == pytest.approx(0.6)

    def test_unknown_route_weight_ignored(self):
        routes = {"A": {D[0]: 100.0}, "ZZZ": {D[0]: 9999.0}}
        assert laspeyres_headline(routes, self.WEIGHTS)[D[0]] == pytest.approx(100.0)

    def test_dates_are_unioned_across_routes(self):
        routes = {"A": {D[0]: 100.0}, "B": {D[1]: 110.0}}
        out = laspeyres_headline(routes, self.WEIGHTS)
        assert sorted(out) == [D[0], D[1]]


class TestBasePeriod:
    def test_rebase_uses_geometric_mean_of_the_window(self):
        # GM(100, 400) = 200 -> rebased to 50 and 200.
        out = rebase_to_period_mean({D[0]: 100.0, D[1]: 400.0}, [D[0], D[1]])
        assert out[D[0]] == pytest.approx(50.0)
        assert out[D[1]] == pytest.approx(200.0)

    def test_single_day_base_is_supported_but_is_the_fragile_case(self):
        out = rebase_to_period_mean({D[0]: 250.0, D[1]: 500.0}, [D[0]])
        assert out[D[0]] == pytest.approx(100.0)
        assert out[D[1]] == pytest.approx(200.0)

    def test_rebasing_preserves_all_ratios(self):
        series = {D[0]: 103.0, D[1]: 97.0, D[2]: 111.0}
        out = rebase_to_period_mean(series, [D[0], D[1]])
        assert out[D[2]] / out[D[1]] == pytest.approx(series[D[2]] / series[D[1]])

    def test_base_window_mean_is_exactly_100(self):
        import math

        series = {D[0]: 103.0, D[1]: 97.0, D[2]: 111.0}
        out = rebase_to_period_mean(series, [D[0], D[1], D[2]])
        gm = math.exp(sum(math.log(out[d]) for d in series) / 3)
        assert gm == pytest.approx(100.0)

    def test_empty_base_window_rejected(self):
        with pytest.raises(ValueError, match="no valid observations"):
            rebase_to_period_mean({D[0]: 100.0}, [D[5]])

    def test_select_base_periods_picks_first_clean_run(self):
        coverage = {D[0]: 0.5, D[1]: 1.0, D[2]: 1.0, D[3]: 0.4, D[4]: 1.0, D[5]: 1.0}
        assert select_base_periods(coverage, n_days=2, min_coverage=0.95) == [D[1], D[2]]

    def test_select_base_periods_requires_consecutive_clean_days(self):
        coverage = {D[0]: 1.0, D[1]: 0.1, D[2]: 1.0, D[3]: 1.0, D[4]: 1.0}
        assert select_base_periods(coverage, n_days=3, min_coverage=0.95) == [D[2], D[3], D[4]]

    def test_select_base_periods_relaxes_rather_than_failing(self):
        coverage = {D[0]: 0.2, D[1]: 0.3, D[2]: 0.4}
        assert select_base_periods(coverage, n_days=2, min_coverage=0.95) == [D[0], D[1]]
