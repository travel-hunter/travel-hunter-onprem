from datetime import date, datetime

import httpx
import pytest

from app.services.travelmonth_collection import CollectionResult


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0
        self.flushes = 0

    def flush(self) -> None:
        self.flushes += 1

    def commit(self) -> None:
        self.commits += 1


def test_live_collector_regional_source_url_uses_vacation_benefit_page() -> None:
    from app.services import travelmonth_live_collector

    assert (
        travelmonth_live_collector.TRAVELMONTH_REGIONAL_BENEFIT_URL
        == "https://korean.visitkorea.or.kr/travelmonth/benefits/vacation-benefit.do"
    )


def test_live_collector_fetches_official_page_and_collects_html(monkeypatch) -> None:
    from app.services import travelmonth_live_collector

    captured = {}

    def fake_get(url, *, timeout, follow_redirects, headers):
        captured["request"] = {
            "url": url,
            "timeout": timeout,
            "follow_redirects": follow_redirects,
            "headers": headers,
        }
        return httpx.Response(
            200,
            text="<section data-benefit-item></section>",
            request=httpx.Request("GET", url),
        )

    def fake_collect(db, html, *, fetched_at, today):
        captured["collection"] = {
            "db": db,
            "html": html,
            "fetched_at": fetched_at,
            "today": today,
        }
        return CollectionResult(
            source_name="여행가는 달",
            source_category="regional_benefit",
            parsed_count=1,
            created_or_updated_count=1,
        )

    monkeypatch.setattr(travelmonth_live_collector.httpx, "get", fake_get)
    monkeypatch.setattr(
        travelmonth_live_collector,
        "collect_regional_benefits_from_html",
        fake_collect,
    )

    db = FakeDb()
    fetched_at = datetime(2026, 5, 21, 10, 30, 0)
    result = travelmonth_live_collector.collect_regional_benefits_from_live_source(
        db,
        fetched_at=fetched_at,
        today=date(2026, 5, 21),
    )

    assert captured["request"]["url"] == travelmonth_live_collector.TRAVELMONTH_REGIONAL_BENEFIT_URL
    assert captured["request"]["timeout"] == 10.0
    assert captured["request"]["follow_redirects"] is True
    assert "Travel Hunter" in captured["request"]["headers"]["User-Agent"]
    assert captured["collection"] == {
        "db": db,
        "html": "<section data-benefit-item></section>",
        "fetched_at": fetched_at,
        "today": date(2026, 5, 21),
    }
    assert result.parsed_count == 1
    assert result.created_or_updated_count == 1


def test_live_collector_wraps_fetch_errors(monkeypatch) -> None:
    from app.services import travelmonth_live_collector

    def fake_get(url, *, timeout, follow_redirects, headers):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(travelmonth_live_collector.httpx, "get", fake_get)

    with pytest.raises(travelmonth_live_collector.TravelMonthLiveFetchError) as exc_info:
        travelmonth_live_collector.collect_regional_benefits_from_live_source(
            FakeDb(),
            fetched_at=datetime(2026, 5, 21, 10, 30, 0),
            today=date(2026, 5, 21),
        )

    assert "Failed to fetch TravelMonth regional benefits" in str(exc_info.value)


def test_live_collector_allows_empty_parse_results(monkeypatch) -> None:
    from app.services import travelmonth_live_collector

    def fake_get(url, *, timeout, follow_redirects, headers):
        return httpx.Response(
            200,
            text="<html><body>unexpected official page shape</body></html>",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(travelmonth_live_collector.httpx, "get", fake_get)

    result = travelmonth_live_collector.collect_regional_benefits_from_live_source(
        FakeDb(),
        fetched_at=datetime(2026, 5, 21, 10, 30, 0),
        today=date(2026, 5, 21),
    )

    assert result.parsed_count == 0
    assert result.created_or_updated_count == 0


def test_collect_travelmonth_once_cli_prints_json_summary(monkeypatch, capsys) -> None:
    from app.scripts import collect_travelmonth_once
    from app.services.external_benefit_collection import (
        ExternalBenefitCollectionResult,
        SourceCollectionResult,
    )

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_session_factory():
        return FakeSession()

    def fake_collect(db, *, timeout):
        assert isinstance(db, FakeSession)
        assert timeout == 15.0
        return ExternalBenefitCollectionResult(
            source_name="official external benefits",
            source_category="multiple",
            parsed_count=58,
            created_or_updated_count=58,
            outcome="success",
            sources=[
                SourceCollectionResult(
                    source_category="regional_benefit",
                    parsed_count=58,
                    created_or_updated_count=58,
                    outcome="success",
                )
            ],
        )

    monkeypatch.setattr(collect_travelmonth_once, "get_session_factory", lambda: fake_session_factory)
    monkeypatch.setattr(
        collect_travelmonth_once,
        "collect_external_benefits_from_live_sources",
        fake_collect,
    )

    exit_code = collect_travelmonth_once.main(["--timeout", "15"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"sourceCategory": "multiple"' in captured.out
    assert '"parsedCount": 58' in captured.out
    assert '"createdOrUpdatedCount": 58' in captured.out
    assert '"outcome": "success"' in captured.out
    assert '"sources": [{"createdOrUpdatedCount": 58, "error": null, "outcome": "success", "parsedCount": 58, "sourceCategory": "regional_benefit"}]' in captured.out
