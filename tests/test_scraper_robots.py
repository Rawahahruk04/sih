from __future__ import annotations

import httpx
import pytest

from aipi.collectors.errors import RobotsDisallowed
from aipi.collectors.scraper.robots import RobotsGate


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)  # type: ignore[arg-type]


def test_allows_unlisted_path(monkeypatch: pytest.MonkeyPatch) -> None:
    robots_txt = "User-agent: *\nDisallow: /admin\n"
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(robots_txt))
    gate = RobotsGate()
    gate.check("https://example.com/search")  # must not raise


def test_disallows_blocked_path(monkeypatch: pytest.MonkeyPatch) -> None:
    robots_txt = "User-agent: *\nDisallow: /search\n"
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse(robots_txt))
    gate = RobotsGate()
    with pytest.raises(RobotsDisallowed):
        gate.check("https://example.com/search?x=1")


def test_missing_robots_txt_defaults_to_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResponse("", status_code=404))
    gate = RobotsGate()
    gate.check("https://example.com/anything")  # must not raise


def test_fetch_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*a: object, **k: object) -> None:
        raise httpx.ConnectError("boom", request=None)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx, "get", _raise)
    gate = RobotsGate()
    with pytest.raises(RobotsDisallowed):
        gate.check("https://example.com/anything")


def test_crawl_delay_is_read_from_robots_txt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _FakeResponse("User-agent: *\nCrawl-delay: 12\n")
    )
    gate = RobotsGate()
    assert gate.crawl_delay_s("https://example.com/x", default_s=3.0) == 12.0


def test_caches_across_calls_to_same_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _get(*a: object, **k: object) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse("User-agent: *\nAllow: /\n")

    monkeypatch.setattr(httpx, "get", _get)
    gate = RobotsGate()
    gate.check("https://example.com/a")
    gate.check("https://example.com/b")
    assert calls["n"] == 1
