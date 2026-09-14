from __future__ import annotations

from datetime import UTC, date, datetime

from app.models import ExternalSourceRecord
from app.services.external_benefit_collection import (
    SourceCollectionResult,
    collect_external_benefits_from_html_sources,
    enrich_existing_local_half_trip_detail_fields,
    fetch_local_half_trip_detail_html,
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


def test_collect_live_sources_enriches_digital_tourism_from_partner_api(
    monkeypatch,
) -> None:
    from app.services import digital_tourism_resident_card as dgtour
    from app.services import external_benefit_collection
    from app.services.external_benefit_collection import SourceDefinition

    fetched_urls: list[str] = []
    upserted_sources = []

    monkeypatch.setattr(
        external_benefit_collection,
        "_source_registry",
        lambda: (
            SourceDefinition(
                dgtour.SOURCE_CATEGORY,
                dgtour.SOURCE_URL,
                external_benefit_collection._parser_for(dgtour.SOURCE_CATEGORY),
            ),
        ),
    )

    def fake_fetch(url, *, timeout):
        fetched_urls.append(url)
        return ""

    def fake_upsert(db_arg, sources):
        rows = list(sources)
        upserted_sources.extend(rows)
        return rows

    monkeypatch.setattr(external_benefit_collection, "fetch_external_source_html", fake_fetch)
    monkeypatch.setattr(
        external_benefit_collection,
        "collect_digital_tourism_partner_benefits_by_city",
        lambda *, timeout: {
            "하동": [
                {
                    "memberId": "hadong-1",
                    "categoryName": "식음료",
                    "name": "하동 제휴 카페",
                    "summary": "음료 할인",
                    "detail": "음료 1,000원 할인",
                }
            ]
        },
    )
    monkeypatch.setattr(
        external_benefit_collection.external_source_repository,
        "upsert_external_source_records",
        fake_upsert,
    )

    result = external_benefit_collection.collect_external_benefits_from_live_sources(
        FakeDb(),
        fetched_at=datetime(2026, 7, 24, tzinfo=UTC),
        today=date(2026, 7, 24),
    )

    assert fetched_urls == []
    assert result.outcome == "success"
    assert result.parsed_count == 52
    assert [source.source_category for source in upserted_sources] == [dgtour.SOURCE_CATEGORY] * 52
    hadong = next(source for source in upserted_sources if source.city == "하동")
    assert hadong.raw_payload["partnerBenefits"][0]["name"] == "하동 제휴 카페"
    assert "하동 제휴처 1곳" in hadong.raw_detail_text


def test_fetch_local_half_trip_detail_html_follows_gangjin_ajax_content(
    monkeypatch,
) -> None:
    from app.services import external_benefit_collection

    fetched_urls: list[str] = []

    def fake_fetch(url: str, *, timeout: float) -> str:
        fetched_urls.append(url)
        if url == "https://www.gangjintour.com/main/main.html":
            return """
            <script>
            DataLoad('load_content','','/skin_hub/SKIN006/main/ajax_Fmain.php','','');
            </script>
            """
        return "<dl><dt>참여대상</dt><dd>강진군 외 지역에 거주하는 관광객</dd></dl>"

    monkeypatch.setattr(external_benefit_collection, "fetch_external_source_html", fake_fetch)

    html = fetch_local_half_trip_detail_html(
        "https://www.gangjintour.com/main/main.html",
        timeout=3,
    )

    assert fetched_urls == [
        "https://www.gangjintour.com/main/main.html",
        "https://www.gangjintour.com/skin_hub/SKIN006/main/ajax_Fmain.php",
    ]
    assert "참여대상" in html


def test_fetch_local_half_trip_detail_html_follows_meta_refresh_then_ajax(
    monkeypatch,
) -> None:
    from app.services import external_benefit_collection

    fetched_urls: list[str] = []

    def fake_fetch(url: str, *, timeout: float) -> str:
        fetched_urls.append(url)
        if url == "https://www.gangjintour.com/":
            return """
            <meta http-equiv="refresh" content="0;url=https://www.gangjintour.com/main/main.html">
            """
        if url == "https://www.gangjintour.com/main/main.html":
            return """
            <script>
            DataLoad('load_content','','/skin_hub/SKIN006/main/ajax_Fmain.php','','');
            </script>
            """
        return "<dl><dt>참여대상</dt><dd>강진군 외 지역에 거주하는 관광객</dd></dl>"

    monkeypatch.setattr(external_benefit_collection, "fetch_external_source_html", fake_fetch)

    html = fetch_local_half_trip_detail_html(
        "https://www.gangjintour.com/",
        timeout=3,
    )

    assert fetched_urls == [
        "https://www.gangjintour.com/",
        "https://www.gangjintour.com/main/main.html",
        "https://www.gangjintour.com/skin_hub/SKIN006/main/ajax_Fmain.php",
    ]
    assert "참여대상" in html


def test_enrich_existing_local_half_trip_detail_fields_updates_public_existing_rows(
    monkeypatch,
) -> None:
    from app.services import external_benefit_collection

    record = ExternalSourceRecord(
        source_name="대한민국 반값여행",
        source_type="official_campaign",
        source_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        source_category="local_half_trip",
        external_id="legacy-gangjin",
        canonical_key="legacy-gangjin",
        detail_url="https://www.gangjintour.com/",
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        title="[강진] 대한민국 반값여행 지원",
        organizer_text="강진 지자체",
        organizers=["강진 지자체"],
        region="전남",
        city="강진",
        is_nationwide=False,
        status_text="신청접수중",
        status="active",
        benefit_text="대한민국 반값여행 지원",
        benefit_value_text="최대 20만원 환급",
        benefit_value_type="mixed",
        tags=["지역할인", "강진"],
        inferred_travel_styles=["체험"],
        confidence=70,
        field_completeness=70,
        raw_list_text="강진 반값여행",
        raw_detail_text="강진군 관광지 2개소 이상 방문",
        raw_payload={"notes": "강진군 관광지 2개소 이상 방문"},
        last_fetched_at=datetime(2026, 7, 26, tzinfo=UTC),
        freshness_status="fresh",
    )
    class FakeScalarResult:
        def all(self):
            return [record]

    class FakeQueryDb:
        def scalars(self, statement):
            return FakeScalarResult()

    monkeypatch.setattr(
        external_benefit_collection,
        "fetch_local_half_trip_detail_html",
        lambda url, *, timeout: """
        <dl>
          <dt>참여대상</dt>
          <dd>
            <p>강진군 외 지역에 거주하는 사전신청 관광객 누구나</p>
            <p>※ 단, 완도군, 해남군, 영암군, 장흥군 거주자는 지원 대상 제외</p>
          </dd>
        </dl>
        """,
    )

    updated_count = enrich_existing_local_half_trip_detail_fields(FakeQueryDb(), timeout=3)

    assert updated_count == 1
    assert record.raw_payload["participantTarget"] == (
        "강진군 외 지역에 거주하는 사전신청 관광객 누구나\n"
        "※ 단, 완도군, 해남군, 영암군, 장흥군 거주자는 지원 대상 제외"
    )
    assert record.field_completeness == 95


def test_live_collection_does_not_fetch_disabled_island_source(monkeypatch) -> None:
    from app.services import external_benefit_collection
    from app.services.external_benefit_collection import SourceDefinition

    monkeypatch.setattr(
        external_benefit_collection,
        "_source_registry",
        lambda: (SourceDefinition("island_visit", "https://official.example/island", lambda *_: []),),
    )
    monkeypatch.setattr(external_benefit_collection, "_enabled_source_categories", lambda db: set())
    monkeypatch.setattr(
        external_benefit_collection,
        "fetch_external_source_html",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not fetch disabled source")),
    )

    result = external_benefit_collection.collect_external_benefits_from_live_sources(
        FakeDb(), fetched_at=datetime(2026, 9, 13, tzinfo=UTC), today=date(2026, 9, 13)
    )

    assert result.sources == []
    assert result.outcome == "success"


def test_live_collection_reports_island_parser_change(monkeypatch) -> None:
    from app.services import external_benefit_collection
    from app.services.external_benefit_collection import SourceDefinition
    from app.services.island_visit_parser import IslandVisitParserChangedError

    def changed_parser(*_args):
        raise IslandVisitParserChangedError("label missing")

    monkeypatch.setattr(
        external_benefit_collection,
        "_source_registry",
        lambda: (SourceDefinition("island_visit", "https://official.example/island", changed_parser, required=False),),
    )
    monkeypatch.setattr(external_benefit_collection, "_enabled_source_categories", lambda db: {"island_visit"})
    monkeypatch.setattr(external_benefit_collection, "fetch_external_source_html", lambda *_args, **_kwargs: "changed html")

    result = external_benefit_collection.collect_external_benefits_from_live_sources(
        FakeDb(), fetched_at=datetime(2026, 9, 13, tzinfo=UTC), today=date(2026, 9, 13)
    )

    assert result.outcome == "error"
    assert result.sources[0].outcome == "parser_changed"
