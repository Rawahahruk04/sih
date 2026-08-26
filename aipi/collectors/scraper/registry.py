"""Which sources exist and which are enabled for a given run.

Kept separate from `sites/` so enabling/disabling a source (e.g. dropping an
OTA pending legal review, or a site that started returning CAPTCHAs on every
run) is a one-line config change, not a code change.
"""

from __future__ import annotations

from dataclasses import dataclass

from aipi.collectors.scraper.base import BaseSiteScraper
from aipi.collectors.scraper.sites import AIRLINE_SCRAPERS, OTA_SCRAPERS


@dataclass(frozen=True)
class SourceSpec:
    cls: type[BaseSiteScraper]
    enabled: bool
    kind: str  # "airline" | "ota"


#: Airlines default ON: single-carrier direct sites, lower ToS ambiguity.
#: OTAs default OFF: verify robots.txt/ToS per source before flipping to True
#: (see aipi/collectors/scraper/sites/otas.py docstring).
REGISTRY: tuple[SourceSpec, ...] = tuple(
    SourceSpec(cls=cls, enabled=True, kind="airline") for cls in AIRLINE_SCRAPERS
) + tuple(
    SourceSpec(cls=cls, enabled=False, kind="ota") for cls in OTA_SCRAPERS
)


def enabled_scrapers(*, include_otas: bool = False) -> list[type[BaseSiteScraper]]:
    return [
        spec.cls
        for spec in REGISTRY
        if spec.enabled and (include_otas or spec.kind == "airline")
    ]


def all_scrapers() -> list[type[BaseSiteScraper]]:
    return [spec.cls for spec in REGISTRY]
