"""MoSPI CPI Transport reference: loading, gaps, and the independence of
"the reference is real" from "the fares are real".

That second point is the one worth guarding with tests. It is the easiest
misreading in the whole project: a report containing one genuine government
series looks like a validated result even when every fare in it is simulated.
"""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from aipi.validation.cpi_reference import (
    CpiReferenceError,
    load_cpi_reference,
)
from aipi.validation.report import build_validation_report

# --- loader ----------------------------------------------------------------


@pytest.fixture(scope="module")
def cpi():
    return load_cpi_reference()


def test_loads_the_real_file(cpi) -> None:
    assert len(cpi.series) == 152
    assert cpi.first_period == "2013-01"
    assert cpi.last_period == "2025-11"
    assert cpi.base_year == "2012=100"


def test_reference_is_flagged_real_not_placeholder(cpi) -> None:
    assert cpi.is_placeholder is False


def test_source_note_is_built_from_the_files_provenance_fields(cpi) -> None:
    assert "MoSPI" in cpi.source_note
    assert "Consumer Price Index" in cpi.source_note
    assert "esankhyiki" in cpi.source_note


def test_covid_gaps_are_absent_not_zero_or_interpolated(cpi) -> None:
    """April/May 2020 had no field collection. They must not exist at all.

    A zero would plot as a total price collapse; an interpolated value would
    fabricate an observation MoSPI never made, in the exact months when the
    underlying prices moved most violently.
    """
    for missing in ("2020-04", "2020-05"):
        assert missing not in cpi.series
        assert cpi.series.get(missing) != 0.0
        assert missing in cpi.gaps


def test_all_three_gaps_are_detected(cpi) -> None:
    """The file has a third gap (April 2019) beyond the two COVID months."""
    assert cpi.gaps == ["2019-04", "2020-04", "2020-05"]


def test_no_rows_were_skipped_on_the_real_file(cpi) -> None:
    assert cpi.skipped == []


def test_periods_are_unique_and_well_formed(cpi) -> None:
    periods = list(cpi.series)
    assert len(periods) == len(set(periods))
    for p in periods:
        year, month = p.split("-")
        assert len(year) == 4 and 1 <= int(month) <= 12


def test_gaps_do_not_break_month_on_month_pairing(cpi) -> None:
    """A gap must break the pair that spans it, not silently bridge it.

    Comparing March 2020 to June 2020 as if it were one month's movement would
    compress a quarter of change into a single reading.
    """
    from aipi.validation.backtest import pct_change

    changes = pct_change(cpi.series)
    # The month after each gap has no immediate predecessor, so `pct_change`
    # must not emit a value keyed on it that pretends otherwise.
    assert "2020-04" not in changes
    assert "2020-05" not in changes


# --- malformed input -------------------------------------------------------


def _write(tmp_path, payload) -> str:
    p = tmp_path / "cpi.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return str(p)


def test_bad_rows_are_skipped_with_reasons_not_fatal(tmp_path) -> None:
    path = _write(
        tmp_path,
        {
            "_base_year": "2012=100",
            "_is_placeholder": False,
            "series": [
                {"period": "2025-01", "transport_communication_index": 171.4},
                {"period": "2025-13", "transport_communication_index": 1.0},
                {"period": "not-a-date", "transport_communication_index": 1.0},
                {"period": "2025-02", "transport_communication_index": "abc"},
                {"period": "2025-03", "transport_communication_index": None},
                {"period": "2025-04", "transport_communication_index": -5.0},
                {"period": "2025-05", "transport_communication_index": 172.8},
            ],
        },
    )
    ref = load_cpi_reference(path)
    assert set(ref.series) == {"2025-01", "2025-05"}
    assert len(ref.skipped) == 5
    joined = " ".join(ref.skipped)
    for expected in ("2025-13", "not-a-date", "abc", "absent", "positive"):
        assert expected in joined


def test_duplicate_period_is_refused_not_overwritten(tmp_path) -> None:
    path = _write(
        tmp_path,
        {
            "_is_placeholder": False,
            "series": [
                {"period": "2025-01", "transport_communication_index": 100.0},
                {"period": "2025-01", "transport_communication_index": 999.0},
            ],
        },
    )
    ref = load_cpi_reference(path)
    assert ref.series["2025-01"] == 100.0, "second occurrence must not win"
    assert any("duplicate" in s for s in ref.skipped)


def test_missing_file_raises(tmp_path) -> None:
    with pytest.raises(CpiReferenceError):
        load_cpi_reference(tmp_path / "nope.json")


def test_empty_series_raises(tmp_path) -> None:
    with pytest.raises(CpiReferenceError):
        load_cpi_reference(_write(tmp_path, {"series": []}))


def test_placeholder_flag_defaults_to_true_when_absent(tmp_path) -> None:
    """An unlabelled file is assumed placeholder — fail toward caution."""
    path = _write(
        tmp_path,
        {"series": [{"period": "2025-01", "transport_communication_index": 100.0}]},
    )
    assert load_cpi_reference(path).is_placeholder is True


# --- the independence property --------------------------------------------


def _tiny_report(cpi_ref, *, data_mode: str):
    """A minimal report over two months of fares with a chosen lineage."""
    daily = {date(2026, 6, 1 + i): 100.0 + i for i in range(28)}
    daily.update({date(2026, 7, 1 + i): 105.0 + i for i in range(28)})
    rows = pd.DataFrame({"data_mode": [data_mode] * 40})
    reference = pd.DataFrame(
        [
            {"period": "2026-06", "route_code": "DEL-BOM", "avg_fare": 5000.0,
             "is_placeholder": True},
            {"period": "2026-07", "route_code": "DEL-BOM", "avg_fare": 5200.0,
             "is_placeholder": True},
        ]
    )
    return build_validation_report(
        daily_index=daily,
        route_index={"DEL-BOM": daily},
        reference=reference,
        route_weights={"DEL-BOM": 1.0},
        contributing_rows=rows,
        cpi_reference=cpi_ref,
    )


def test_real_reference_does_not_make_synthetic_fares_real(cpi) -> None:
    """The acceptance criterion: both facts visible, neither overwriting the other."""
    report = _tiny_report(cpi, data_mode="synthetic")

    # The reference is real...
    assert report.secondary_reference["is_placeholder"] is False
    # ...and the fares are still synthetic.
    assert report.data_mode["synthetic"] == pytest.approx(1.0)
    assert report.data_mode["real"] == pytest.approx(0.0)
    assert report.is_fully_synthetic is True
    assert "SYNTHETIC" in report.headline_caveat()


def test_a_note_explicitly_separates_the_two_claims(cpi) -> None:
    report = _tiny_report(cpi, data_mode="synthetic")
    joined = " ".join(report.notes)
    assert "SCOPE OF THE 'REAL' LABEL" in joined
    assert "data_mode_breakdown" in joined


def test_caveat_tracks_fares_when_they_are_real(cpi) -> None:
    """Inverse control: with real fares the caveat changes, independent of the
    reference's own flag."""
    report = _tiny_report(cpi, data_mode="real")
    assert report.data_mode["real"] == pytest.approx(1.0)
    assert "SYNTHETIC fares" not in report.headline_caveat()
    # The secondary reference's flag is unchanged by the fares' lineage.
    assert report.secondary_reference["is_placeholder"] is False


def test_secondary_block_is_absent_when_no_cpi_supplied() -> None:
    report = _tiny_report(None, data_mode="synthetic")
    assert report.secondary_reference is None
    assert report.to_dict()["secondary_reference"] is None


# --- the overlap problem ---------------------------------------------------


def test_no_overlap_reports_zero_rather_than_a_correlation(cpi) -> None:
    """CPI ends 2025-11; the index covers 2026. There are no paired months.

    The correct output is a refusal with the reason stated, not a number.
    """
    report = _tiny_report(cpi, data_mode="synthetic")
    s = report.secondary_reference
    assert s["overlap_months"] == 0
    assert s["n_paired_movements"] == 0
    assert s["pearson_r"] is None
    assert s["insufficient_n"] is True
    assert any("NO TEMPORAL OVERLAP" in n for n in s["notes"])


def test_estimand_mismatch_is_disclosed(cpi) -> None:
    """Transport & Communication includes fuel, rail and telecom, not just air."""
    report = _tiny_report(cpi, data_mode="synthetic")
    joined = " ".join(report.secondary_reference["notes"])
    assert "small component" in joined
    assert "NOT a like-for-like validation" in joined


def test_overlap_produces_paired_series_when_periods_align(cpi, tmp_path) -> None:
    """Positive control: the machinery does pair up when the months do overlap.

    Without this, every assertion above would pass on a comparison that could
    never work at all.
    """
    path = _write(
        tmp_path,
        {
            "_base_year": "2012=100",
            "_is_placeholder": False,
            "series": [
                {"period": "2026-06", "transport_communication_index": 172.0},
                {"period": "2026-07", "transport_communication_index": 173.5},
            ],
        },
    )
    aligned = load_cpi_reference(path)
    report = _tiny_report(aligned, data_mode="synthetic")
    s = report.secondary_reference
    assert s["overlap_months"] == 2
    assert s["n_paired_movements"] == 1
    assert len(s["series"]) == 2
    assert {p["period"] for p in s["series"]} == {"2026-06", "2026-07"}
    # n=1 is still below the reporting threshold, and must still be refused.
    assert s["insufficient_n"] is True
