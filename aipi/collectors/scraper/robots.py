"""robots.txt compliance gate.

The problem statement requires remaining "compliant with the robots.txt and
terms of service of source websites." That is not a checkbox — it is a hard
gate every request passes through before it is issued, checked against the
*live* robots.txt (fetched with a short cache, not vendored), because a
publisher can change crawl policy at any time and a stale local copy would
silently start violating it.

If a source's robots.txt disallows a path this project needs, the fix is to
drop that source or negotiate direct access — never to bypass the check.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import httpx

from aipi.collectors.errors import RobotsDisallowed

log = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "AIPI-ResearchBot/0.1 (+https://github.com/aipi/aipi; MoSPI SIH 2026 PS 26056)"
CACHE_TTL_S = 3600.0


@dataclass
class _CacheEntry:
    parser: robotparser.RobotFileParser
    fetched_at: float
    crawl_delay: float | None


@dataclass
class RobotsGate:
    """Per-origin robots.txt cache with a hard allow/deny check.

    One instance is shared across a whole collection run so the txt is fetched
    once per origin per `CACHE_TTL_S`, not once per URL.
    """

    user_agent: str = DEFAULT_USER_AGENT
    timeout_s: float = 15.0
    _cache: dict[str, _CacheEntry] = field(default_factory=dict, repr=False)

    def _origin(self, url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"

    def _load(self, origin: str) -> _CacheEntry:
        cached = self._cache.get(origin)
        now = time.monotonic()
        if cached is not None and (now - cached.fetched_at) < CACHE_TTL_S:
            return cached

        parser = robotparser.RobotFileParser()
        robots_url = urljoin(origin + "/", "robots.txt")
        try:
            resp = httpx.get(
                robots_url, timeout=self.timeout_s, headers={"User-Agent": self.user_agent}
            )
            if resp.status_code == 404:
                # No robots.txt published: RFC 9309 default is "everything allowed".
                parser.parse([])
            else:
                resp.raise_for_status()
                parser.parse(resp.text.splitlines())
        except httpx.HTTPError as exc:
            # Fetch failure is NOT permission. Fail closed: treat as fully
            # disallowed until the txt is fetchable, rather than assuming access.
            log.warning("robots.txt fetch failed for %s (%s); failing closed", origin, exc)
            parser.parse(["User-agent: *", "Disallow: /"])

        delay = parser.crawl_delay(self.user_agent)
        entry = _CacheEntry(parser=parser, fetched_at=now, crawl_delay=delay)
        self._cache[origin] = entry
        return entry

    def check(self, url: str) -> None:
        """Raise `RobotsDisallowed` if `url` is not fetchable under robots.txt."""
        origin = self._origin(url)
        entry = self._load(origin)
        if not entry.parser.can_fetch(self.user_agent, url):
            raise RobotsDisallowed(
                f"robots.txt at {origin}/robots.txt disallows {url} for "
                f"user-agent '{self.user_agent}'. Not fetching."
            )

    def crawl_delay_s(self, url: str, default_s: float) -> float:
        """Publisher-declared minimum spacing, or our own default if silent."""
        entry = self._load(self._origin(url))
        return entry.crawl_delay if entry.crawl_delay is not None else default_s
