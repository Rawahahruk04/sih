"""The six OTAs named in PS 26056.

OTAs are the higher-risk half of this module: search-API endpoints redesign
more often than an airline's own site, and several major OTAs run aggressive
bot-detection (Akamai/PerimeterX/Cloudflare challenge pages) in front of their
search flow — which is exactly what `CaptchaEncountered` in
`aipi.collectors.scraper.base` is there to detect and stop on, not push
through. Before enabling any of these in a scheduled run, re-read that site's
robots.txt and Terms of Use for an explicit no-scraping clause; `RobotsGate`
enforces robots.txt automatically, but a ToS prohibition that robots.txt does
not encode is a legal question this code cannot answer for you — treat OTA
sources as opt-in per the outcome of that review, not on-by-default.

Aggregators (`IS_AGGREGATOR = True`) report `carrier` from the payload itself
rather than a fixed code, since one OTA search spans many airlines.
"""

from __future__ import annotations

from datetime import date

from aipi.collectors.scraper.base import BaseSiteScraper
from aipi.collectors.scraper.heuristics import generic_parse


class MakeMyTripScraper(BaseSiteScraper):
    SOURCE_NAME = "makemytrip"
    BASE_URL = "https://www.makemytrip.com"
    RESULT_URL_SUBSTRING = "/api/flights/search"  # verify against live network tab
    IS_AGGREGATOR = True

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        d = departure.strftime("%d%m%Y")
        return (
            f"{self.BASE_URL}/flight/search?itinerary={origin}-{destination}-{d}"
            "&tripType=O&paxType=A-1_C-0_I-0&cabinClass=E"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=None,
        )


class YatraScraper(BaseSiteScraper):
    SOURCE_NAME = "yatra"
    BASE_URL = "https://www.yatra.com"
    RESULT_URL_SUBSTRING = "/flights/search"  # verify against live network tab
    IS_AGGREGATOR = True

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        d = departure.strftime("%d-%m-%Y")
        return (
            f"{self.BASE_URL}/air/results?src={origin}&dest={destination}"
            f"&adt=1&chd=0&inf=0&cabin=Economy&onward={d}&flexi=false"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=None,
        )


class EaseMyTripScraper(BaseSiteScraper):
    SOURCE_NAME = "easemytrip"
    BASE_URL = "https://www.easemytrip.com"
    RESULT_URL_SUBSTRING = "/flight/Search/FlightSearch"
    IS_AGGREGATOR = True

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        d = departure.strftime("%d-%m-%Y")
        srch = f"{origin}-{origin}|{destination}-{destination}|{d}"
        return f"{self.BASE_URL}/flight/results?srch={srch}&px=1-0-0&cbn=0&ar=undefined"

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=None,
        )


class ClearTripScraper(BaseSiteScraper):
    SOURCE_NAME = "cleartrip"
    BASE_URL = "https://www.cleartrip.com"
    RESULT_URL_SUBSTRING = "/api/flight/search"  # verify against live network tab
    IS_AGGREGATOR = True

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        d = departure.isoformat()
        return (
            f"{self.BASE_URL}/flights/results?adults=1&childs=0&infants=0"
            f"&class=Economy&depart_date={d}&from={origin}&to={destination}&intl=false&sft=O"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=None,
        )


class IxigoScraper(BaseSiteScraper):
    SOURCE_NAME = "ixigo"
    BASE_URL = "https://www.ixigo.com"
    RESULT_URL_SUBSTRING = "/api/search"  # verify against live network tab
    IS_AGGREGATOR = True

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        d = departure.isoformat()
        return (
            f"{self.BASE_URL}/search/result/flight?from={origin}&to={destination}&date={d}"
            "&returnDate=&adults=1&children=0&infants=0&class=e&source=Search+Form"
        )

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=None,
        )


class GoibiboScraper(BaseSiteScraper):
    SOURCE_NAME = "goibibo"
    BASE_URL = "https://www.goibibo.com"
    RESULT_URL_SUBSTRING = "/api/flights"  # verify against live network tab
    IS_AGGREGATOR = True

    def search_url(self, origin: str, destination: str, departure: date) -> str:
        d = departure.strftime("%d%m%Y")
        return f"{self.BASE_URL}/flights/air-{origin.lower()}-{destination.lower()}-{d}--1-0-0-E-D/"

    def parse(self, payload, *, origin, destination, departure) -> list[dict]:
        return generic_parse(
            payload, origin=origin, destination=destination, departure=departure,
            source=self.SOURCE_NAME, default_carrier=None,
        )


OTA_SCRAPERS: tuple[type[BaseSiteScraper], ...] = (
    MakeMyTripScraper,
    YatraScraper,
    EaseMyTripScraper,
    ClearTripScraper,
    IxigoScraper,
    GoibiboScraper,
)
