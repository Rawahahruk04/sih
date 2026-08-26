from __future__ import annotations

from datetime import date

import pytest

from aipi.collectors.errors import CollectionError
from aipi.collectors.scraper.heuristics import generic_parse
from aipi.collectors.synthetic import RAW_COLUMNS


def test_parses_common_shape() -> None:
    payload = {
        "results": [
            {
                "carrier": "6E",
                "flightNumber": "6E-204",
                "totalFare": "5230.00",
                "baseFare": "4500",
                "tax": "730",
                "fareBrand": "SAVER",
                "cabin": "economy",
            },
            {
                "carrier": "6E",
                "flightNumber": "6E-517",
                "totalFare": "6110",
                "fareBrand": "FLEXI",
            },
        ]
    }
    rows = generic_parse(
        payload,
        origin="DEL",
        destination="BOM",
        departure=date(2026, 9, 10),
        source="indigo_site",
        default_carrier="6E",
    )
    assert len(rows) == 2
    for row in rows:
        assert set(row) == set(RAW_COLUMNS)
    assert rows[0]["total_fare"] == 5230.0
    assert rows[0]["base_fare"] == 4500.0
    assert rows[0]["taxes"] == 730.0
    assert rows[0]["source"] == "indigo_site"
    assert rows[0]["origin"] == "DEL"
    assert rows[0]["advance_days"] == (date(2026, 9, 10) - date.today()).days


def test_nested_container_is_found() -> None:
    payload = {"data": {"flights": [{"total_price": 4999, "airline": "SG"}]}}
    rows = generic_parse(
        payload, origin="DEL", destination="HYD", departure=date(2026, 9, 12),
        source="spicejet_site", default_carrier=None,
    )
    assert len(rows) == 1
    assert rows[0]["total_fare"] == 4999.0
    assert rows[0]["carrier"] == "SG"


def test_no_offer_list_raises_collection_error() -> None:
    with pytest.raises(CollectionError):
        generic_parse(
            {"status": "ok", "message": "no results"},
            origin="DEL", destination="BOM", departure=date(2026, 9, 10),
            source="x", default_carrier=None,
        )


def test_no_recognisable_fare_field_raises_collection_error() -> None:
    payload = {"results": [{"foo": "bar"}, {"baz": 1}]}
    with pytest.raises(CollectionError):
        generic_parse(
            payload, origin="DEL", destination="BOM", departure=date(2026, 9, 10),
            source="x", default_carrier=None,
        )


def test_default_carrier_used_when_payload_omits_it() -> None:
    payload = {"results": [{"totalFare": 5000}]}
    rows = generic_parse(
        payload, origin="DEL", destination="BOM", departure=date(2026, 9, 10),
        source="indigo_site", default_carrier="6E",
    )
    assert rows[0]["carrier"] == "6E"
