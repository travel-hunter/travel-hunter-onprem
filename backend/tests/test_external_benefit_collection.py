from __future__ import annotations

from datetime import UTC, date, datetime

from app.services.external_benefit_collection import (
    SourceCollectionResult,
    collect_external_benefits_from_html_sources,
)


class FakeDb:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


def test_collect_external_benefits_from_html_sources_upserts_successful_sources(
    monkeypatch,
) -> None:
    calls: list[str] = []

    def fake_upsert(db_arg, sources):
        rows = list(sources)
        calls.extend(source.source_category for source in rows)
        return rows

    monkeypatch.setattr(
        "app.services.external_benefit_collection.external_source_repository.upsert_external_source_records",
        fake_upsert,
    )
    monkeypatch.setattr(
        "app.services.external_benefit_collection.policy_normalization.promote_external_benefits_to_policies",
        lambda db_arg: None,
    )

    db = FakeDb()
    result = collect_external_benefits_from_html_sources(
        db,
        html_sources={
            "regional_benefit": "<html></html>",
            "traffic_benefit": "<h4>테마열차 할인</h4><p>운임료 50% 할인</p>",
            "local_half_trip": (
                "<h2>합천 신청접수중</h2>"
                "<p>신청기간 : 2026.05.20-2026.06.30</p>"
                "<p>여행기간 : 2026.06.01~2026.06.30</p>"
            ),
            "stay_discount": (
                "<section data-stay-discount><h2>숙박세일 페스타</h2>"
                "<p>입실기간 : 6월 11일 ~ 7월 31일</p>"
                "<p>혜택 : 2/3/5/7만원 숙박 할인</p></section>"
            ),
        },
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert isinstance(result.sources[0], SourceCollectionResult)
    assert "traffic_benefit" in calls
    assert "local_half_trip" in calls
    assert "stay_discount" in calls
    assert result.outcome == "success"
    assert result.created_or_updated_count == len(calls)
    assert db.commits == 1


def test_collect_external_benefits_from_html_sources_reports_partial_success(
    monkeypatch,
) -> None:
    def fake_upsert(db_arg, sources):
        return list(sources)

    monkeypatch.setattr(
        "app.services.external_benefit_collection.external_source_repository.upsert_external_source_records",
        fake_upsert,
    )
    monkeypatch.setattr(
        "app.services.external_benefit_collection.policy_normalization.promote_external_benefits_to_policies",
        lambda db_arg: None,
    )

    result = collect_external_benefits_from_html_sources(
        FakeDb(),
        html_sources={
            "traffic_benefit": "<h4>테마열차 할인</h4><p>운임료 50% 할인</p>",
            "unknown_category": "<html></html>",
        },
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert result.outcome == "partial_success"
    assert result.parsed_count == 1
    assert [source.outcome for source in result.sources] == ["success", "error"]


def test_collect_external_benefits_from_live_sources_marks_404_and_410_source_unavailable(
    monkeypatch,
) -> None:
    import httpx

    from app.services import external_benefit_collection
    from app.services.external_benefit_collection import SourceDefinition

    db = FakeDb()

    def fake_parser(html, fetched_at, today):
        return []

    def fake_upsert(db_arg, sources):
        return list(sources)

    monkeypatch.setattr(
        external_benefit_collection,
        "_source_registry",
        lambda: (
            SourceDefinition("regional_benefit", "https://official.example/404", fake_parser),
            SourceDefinition("local_half_trip", "https://official.example/410", fake_parser),
        ),
    )
    monkeypatch.setattr(
        external_benefit_collection.external_source_repository,
        "upsert_external_source_records",
        fake_upsert,
    )

    def fake_get(url, *, timeout, follow_redirects, headers):
        status_code = 404 if url.endswith("404") else 410
        return httpx.Response(
            status_code,
            text="gone",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(external_benefit_collection.httpx, "get", fake_get)

    result = external_benefit_collection.collect_external_benefits_from_live_sources(
        db,
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert result.outcome == "error"
    assert [source.outcome for source in result.sources] == [
        "source_unavailable",
        "source_unavailable",
    ]
    assert "404" in (result.sources[0].error or "")
    assert "410" in (result.sources[1].error or "")
    assert db.commits == 1


def test_collect_external_benefits_from_live_sources_treats_traffic_as_optional_legacy(
    monkeypatch,
) -> None:
    import httpx

    from app.services import external_benefit_collection
    from app.services.external_benefit_collection import SourceDefinition

    def success_parser(html, fetched_at, today):
        return [type("Source", (), {"source_category": "regional_benefit"})()]

    def traffic_parser(html, fetched_at, today):
        return []

    monkeypatch.setattr(
        external_benefit_collection,
        "_source_registry",
        lambda: (
            SourceDefinition("regional_benefit", "https://official.example/regional", success_parser),
            SourceDefinition(
                "traffic_benefit",
                "https://official.example/traffic-legacy",
                traffic_parser,
                required=False,
            ),
        ),
    )
    monkeypatch.setattr(
        external_benefit_collection.external_source_repository,
        "upsert_external_source_records",
        lambda db_arg, sources: list(sources),
    )
    monkeypatch.setattr(
        external_benefit_collection.policy_normalization,
        "promote_external_benefits_to_policies",
        lambda db_arg: None,
    )

    def fake_get(url, *, timeout, follow_redirects, headers):
        if url.endswith("traffic-legacy"):
            return httpx.Response(
                404,
                text="legacy traffic source removed",
                request=httpx.Request("GET", url),
            )
        return httpx.Response(
            200,
            text="regional html",
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(external_benefit_collection.httpx, "get", fake_get)

    result = external_benefit_collection.collect_external_benefits_from_live_sources(
        FakeDb(),
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert result.outcome == "success"
    assert result.parsed_count == 1
    assert [(source.source_category, source.outcome) for source in result.sources] == [
        ("regional_benefit", "success"),
        ("traffic_benefit", "source_unavailable"),
    ]


def test_collect_external_benefits_from_live_sources_reports_partial_success_for_required_404(
    monkeypatch,
) -> None:
    import httpx

    from app.services import external_benefit_collection
    from app.services.external_benefit_collection import SourceDefinition

    def success_parser(html, fetched_at, today):
        return [type("Source", (), {"source_category": "stay_discount"})()]

    def missing_parser(html, fetched_at, today):
        return []

    monkeypatch.setattr(
        external_benefit_collection,
        "_source_registry",
        lambda: (
            SourceDefinition("regional_benefit", "https://official.example/regional", missing_parser),
            SourceDefinition("stay_discount", "https://official.example/stay", success_parser),
        ),
    )
    monkeypatch.setattr(
        external_benefit_collection.external_source_repository,
        "upsert_external_source_records",
        lambda db_arg, sources: list(sources),
    )
    monkeypatch.setattr(
        external_benefit_collection.policy_normalization,
        "promote_external_benefits_to_policies",
        lambda db_arg: None,
    )

    def fake_get(url, *, timeout, follow_redirects, headers):
        if url.endswith("regional"):
            return httpx.Response(
                404,
                text="regional source moved",
                request=httpx.Request("GET", url),
            )
        return httpx.Response(200, text="stay html", request=httpx.Request("GET", url))

    monkeypatch.setattr(external_benefit_collection.httpx, "get", fake_get)

    result = external_benefit_collection.collect_external_benefits_from_live_sources(
        FakeDb(),
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert result.outcome == "partial_success"
    assert [(source.source_category, source.outcome) for source in result.sources] == [
        ("regional_benefit", "source_unavailable"),
        ("stay_discount", "success"),
    ]
