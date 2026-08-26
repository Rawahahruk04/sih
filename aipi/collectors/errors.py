"""Shared collector exceptions.

Every collector (Duffel, synthetic, site scrapers) raises `CollectionError` on a
capture it must not publish. A short capture that looks like a successful one is
the failure mode that corrupts an index — missing rows are indistinguishable from
a fall in fares — so partial failure is fatal by design across every collector,
not just one.
"""

from __future__ import annotations


class CollectionError(RuntimeError):
    """Collection failed in a way that must not be silently tolerated."""


class RobotsDisallowed(CollectionError):
    """robots.txt forbids the path we were about to fetch.

    Raised, never bypassed. A statistical agency's data pipeline cannot be built
    on a policy of ignoring the publisher's stated crawl policy — if a source
    disallows the paths this project needs, that source is not usable until its
    operator grants access some other way (e.g. an API), not scraped anyway.
    """


class CaptchaEncountered(CollectionError):
    """The page returned a CAPTCHA/anti-bot challenge instead of results.

    This module does not attempt to defeat CAPTCHAs. It detects them, stops, and
    surfaces the event so a human can decide what to do next (back off, rotate
    identity within the site's own rate limits, or drop the source) — solving them
    programmatically is both against the spirit of "ethical scraping" this
    problem statement asks for and a maintenance trap that breaks on every
    provider update.
    """
