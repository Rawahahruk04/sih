"""The five airline direct sites named in PS 26056.

`RESULT_URL_SUBSTRING` and `search_url()` are best-effort as of the date in
each docstring — a direct-site search flow is far more stable than an OTA's
(fewer redesigns, one carrier's own fares only), but still requires the
one-time manual verification described in `docs/SCRAPER_SETUP.md` before a
site is trusted for production capture. Each class defaults to the shared
heuristic parser (`aipi.collectors.scraper.heuristics.generic_parse`); once a
site's real payload has been inspected, replace `parse()` with an exact
mapping for that site instead of relying on the heuristic guesses.
"""

from __future__ import annotations

from datetime import date

from aipi.collectors.scraper.base import BaseSiteScraper
from aipi.collectors.scraper.heuristics import generic_parse


class IndiGoSiteScraper(BaseSiteScraper):
    SOURCE_NAME = "indigo_site"
    BASE_URL = "https://www.goindigo.in"
    RESULT_URL_SUBSTRING = "/api/dapi/search/"  # verify: DevTools > Network on a live search
    CARRIER_CODE = "6E"

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        return (
            f"{self.BASE_URL}/booking/flight-select?"
            f"itineraryType=ONE_WAY&originStation1={origin}&destinationStation1={destination}"
            f"&departureDate1={departure.isoformat()}&adults=1&children=0&infants=0&cabinClass=ECONOMY"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=self.CARRIER_CODE,
        )


class AirIndiaSiteScraper(BaseSiteScraper):
    SOURCE_NAME = "air_india_site"
    BASE_URL = "https://www.airindia.com"
    RESULT_URL_SUBSTRING = "/api/search"  # verify against live network tab
    CARRIER_CODE = "AI"

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        return (
            f"{self.BASE_URL}/en-in/book/flight-search?"
            f"tripType=O&origin={origin}&destination={destination}"
            f"&departDate={departure.isoformat()}&adult=1&cabin=ECONOMY"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=self.CARRIER_CODE,
        )


class AirIndiaExpressSiteScraper(BaseSiteScraper):
    SOURCE_NAME = "air_india_express_site"
    BASE_URL = "https://www.airindiaexpress.com"
    RESULT_URL_SUBSTRING = "/api/search"  # verify against live network tab
    CARRIER_CODE = "IX"

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        return (
            f"{self.BASE_URL}/book/flight-search?tripType=oneway"
            f"&origin={origin}&destination={destination}&departDate={departure.isoformat()}&adults=1"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=self.CARRIER_CODE,
        )


class AkasaAirSiteScraper(BaseSiteScraper):
    SOURCE_NAME = "akasa_site"
    BASE_URL = "https://www.akasaair.com"
    RESULT_URL_SUBSTRING = "/api/flights/availability"
    CARRIER_CODE = "QP"

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        return (
            f"{self.BASE_URL}/book/flight-select?tripType=O"
            f"&from={origin}&to={destination}&departure={departure.isoformat()}&paxAdult=1"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=self.CARRIER_CODE,
        )


class SpiceJetSiteScraper(BaseSiteScraper):
    SOURCE_NAME = "spicejet_site"
    BASE_URL = "https://www.spicejet.com"
    RESULT_URL_SUBSTRING = "/api/v1/search/flight-search"
    CARRIER_CODE = "SG"

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        return (
            f"{self.BASE_URL}/book?"
            f"tripCategory=ONE_WAY&originStationCode={origin}&destinationStationCode={destination}"
            f"&departureDate={departure.isoformat()}&adultCount=1"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=self.CARRIER_CODE,
        )


AIRLINE_SCRAPERS: tuple[type[BaseSiteScraper], ...] = (
    IndiGoSiteScraper,
    AirIndiaSiteScraper,
    AirIndiaExpressSiteScraper,
    AkasaAirSiteScraper,
    SpiceJetSiteScraper,
)
