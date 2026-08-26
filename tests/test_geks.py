"""Tests for the multilateral (GEKS) elementary index.

`TestChainDrift` is the load-bearing test in this repository. It constructs the
exact failure mode that makes a chained daily index unusable, and shows GEKS
returning the right answer to the last decimal place. Every expected value is
derived by hand below.
"""

from __future__ import annotations

import math
from datetime import date

import pytest

from aipi.index.elementary import chained_jevons, jevons_bilateral
from aipi.index.geks import (
    drift_diagnostic,
    geks_coverage,
    geks_jevons,
    log_bilateral_matrix,
    rolling_geks_jevons,
)

D = [date(2026, 8, d) for d in range(1, 32)]


class TestChainDrift:
    r"""An item leaves the sample on sale and returns at full price.

    Panel (2 items priced, one rotating out):

        d0:  A=100  B=100
        d1:  A= 50  B=100      <- A discounted
        d2:          B=100  C=100   <- A withdrawn WHILE CHEAP
        d3:  A=100  B=100      <- A returns at its original price

    Prices at d3 are identical to d0, so any correct index reads 100 at d3.

    Chained Jevons, link by link:
        d0->d1  matched {A,B}:  GM(0.5, 1.0) = 2^-0.5
        d1->d2  matched {B}:    1.0
        d2->d3  matched {B}:    1.0
        => d3 = 100 * 2^-0.5 = 70.71.  The recovery is never observed, because A
           was unmatched at the moment it recovered. The index has ratcheted.

    GEKS. Log-bilateral matrix (ln P(s,t)), with L = ln(2)/2:
        L(0,1) = -L    L(0,2) = 0     L(0,3) = 0
        L(1,2) =  0    L(1,3) = +L
        L(2,3) =  0
      Column means m(t) = mean_s L(s,t) over 4 rows:
        m0 = (0 + L + 0 + 0)/4 =  L/4
        m1 = (-L + 0 + 0 - L)/4 = -L/2
        m2 = 0
        m3 = (0 + L + 0 + 0)/4 =  L/4
      ln P_GEKS(0,t) = m(t) - m(0):
        d0:  0                    -> 100
        d1: -L/2 - L/4 = -3L/4    -> 100 * 2^-0.375 = 77.1105
        d2:  0   - L/4 = -L/4     -> 100 * 2^-0.125 = 91.7004
        d3:  0                    -> 100    EXACTLY
    """

    PANEL = {
        D[0]: {"A": 100.0, "B": 100.0},
        D[1]: {"A": 50.0, "B": 100.0},
        D[2]: {"B": 100.0, "C": 100.0},
        D[3]: {"A": 100.0, "B": 100.0},
    }

    def test_chained_index_drifts(self):
        chained = chained_jevons(self.PANEL, min_matched=1)
        assert chained[D[3]] == pytest.approx(100.0 * 2**-0.5)
        assert chained[D[3]] == pytest.approx(70.7107, abs=1e-4)

    def test_geks_returns_exactly_100(self):
        geks = geks_jevons(self.PANEL, min_matched=1)
        assert geks[D[3]] == pytest.approx(100.0, abs=1e-9)

    def test_geks_intermediate_values_match_hand_derivation(self):
        geks = geks_jevons(self.PANEL, min_matched=1)
        assert geks[D[0]] == pytest.approx(100.0)
        assert geks[D[1]] == pytest.approx(100.0 * 2**-0.375)
        assert geks[D[2]] == pytest.approx(100.0 * 2**-0.125)
        assert geks[D[1]] == pytest.approx(77.1105, abs=1e-4)
        assert geks[D[2]] == pytest.approx(91.7004, abs=1e-4)

    def test_drift_diagnostic_quantifies_the_gap(self):
        chained = chained_jevons(self.PANEL, min_matched=1)
        geks = geks_jevons(self.PANEL, min_matched=1)
        diag = drift_diagnostic(chained, geks)
        # Chained ends 29.3% below the drift-free answer.
        assert diag["end_gap_pct"] == pytest.approx(-29.2893, abs=1e-3)
        assert diag["n"] == 4.0


class TestGeksProperties:
    STABLE = {
        D[0]: {"a": 4000.0, "b": 9000.0, "c": 12_000.0},
        D[1]: {"a": 4400.0, "b": 8500.0, "c": 13_000.0},
        D[2]: {"a": 4100.0, "b": 9900.0, "c": 11_500.0},
        D[3]: {"a": 5000.0, "b": 9200.0, "c": 12_800.0},
    }

    def test_equals_chained_jevons_when_item_set_never_changes(self):
        """With a fixed item set Jevons is already transitive, so the two
        independent code paths must agree exactly. A genuine cross-check."""
        geks = geks_jevons(self.STABLE, min_matched=1)
        chained = chained_jevons(self.STABLE, min_matched=1)
        for d in self.STABLE:
            assert geks[d] == pytest.approx(chained[d])

    def test_equals_direct_bilateral_when_item_set_never_changes(self):
        geks = geks_jevons(self.STABLE, min_matched=1)
        for d in self.STABLE:
            direct = jevons_bilateral(self.STABLE[D[0]], self.STABLE[d], min_matched=1)
            assert geks[d] == pytest.approx(100.0 * direct)

    def test_transitivity(self):
        """P(s,u) * P(u,t) == P(s,t) for all triples — GEKS cannot drift."""
        geks = geks_jevons(self.STABLE, min_matched=1)
        for s in self.STABLE:
            for u in self.STABLE:
                for t in self.STABLE:
                    lhs = (geks[u] / geks[s]) * (geks[t] / geks[u])
                    assert lhs == pytest.approx(geks[t] / geks[s])

    def test_uniform_inflation_is_reproduced_exactly(self):
        panel = {
            D[i]: {"a": 1000.0 * 1.01**i, "b": 7000.0 * 1.01**i} for i in range(6)
        }
        geks = geks_jevons(panel, min_matched=1)
        for i in range(6):
            assert geks[D[i]] == pytest.approx(100.0 * 1.01**i)

    def test_scale_invariance(self):
        """Doubling every fare in every period must not move the index."""
        doubled = {d: {k: v * 2 for k, v in prices.items()} for d, prices in self.STABLE.items()}
        a = geks_jevons(self.STABLE, min_matched=1)
        b = geks_jevons(doubled, min_matched=1)
        for d in self.STABLE:
            assert a[d] == pytest.approx(b[d])

    def test_empty_and_single_period(self):
        assert geks_jevons({}) == {}
        assert geks_jevons({D[0]: {"a": 1.0}}) == {D[0]: 100.0}


class TestBilateralMatrix:
    def test_antisymmetric_with_zero_diagonal(self):
        panel = {
            D[0]: {"a": 100.0, "b": 200.0},
            D[1]: {"a": 110.0, "b": 210.0},
            D[2]: {"a": 105.0, "b": 190.0},
        }
        periods = sorted(panel)
        m = log_bilateral_matrix(panel, periods, min_matched=1)
        for i in range(3):
            assert m[i, i] == 0.0
            for j in range(3):
                assert m[i, j] == pytest.approx(-m[j, i])

    def test_unestimable_pairs_are_nan_and_reported_in_coverage(self):
        panel = {
            D[0]: {"a": 100.0},
            D[1]: {"z": 100.0},  # shares nothing with the others
            D[2]: {"a": 120.0},
        }
        periods = sorted(panel)
        m = log_bilateral_matrix(panel, periods, min_matched=1)
        assert math.isnan(m[0, 1])
        assert math.isnan(m[1, 2])
        assert m[0, 2] == pytest.approx(math.log(1.2))
        # 2 of 6 off-diagonal pairs estimable.
        assert geks_coverage(m) == pytest.approx(2 / 6)

    def test_index_still_produced_from_partial_coverage(self):
        panel = {
            D[0]: {"a": 100.0},
            D[1]: {"z": 100.0},
            D[2]: {"a": 120.0},
        }
        geks = geks_jevons(panel, min_matched=1)
        assert set(geks) == set(panel)
        assert geks[D[2]] > geks[D[0]]


class TestRollingWindow:
    @staticmethod
    def _panel(n: int, drift: float = 1.002) -> dict[date, dict[str, float]]:
        return {
            D[i]: {"a": 5000.0 * drift**i, "b": 9000.0 * drift**i} for i in range(n)
        }

    def test_short_series_uses_full_window(self):
        panel = self._panel(5)
        assert rolling_geks_jevons(panel, window=25, min_matched=1) == pytest.approx(
            geks_jevons(panel, min_matched=1)
        )

    def test_published_values_are_never_revised(self):
        """Adding tomorrow must not change any value already published."""
        panel = self._panel(20)
        first = rolling_geks_jevons(panel, window=10, min_matched=1)
        panel_next = self._panel(21)
        second = rolling_geks_jevons(panel_next, window=10, min_matched=1)
        for d in first:
            assert first[d] == pytest.approx(second[d]), f"revised {d}"

    def test_tracks_known_inflation_across_window_splices(self):
        panel = self._panel(20, drift=1.002)
        series = rolling_geks_jevons(panel, window=8, min_matched=1)
        assert series[D[19]] == pytest.approx(100.0 * 1.002**19, rel=1e-9)
