from datetime import UTC, date, datetime

import pytest


def test_parse_island_visit_support_builds_one_campaign_candidate() -> None:
    from app.services.island_visit_parser import parse_island_visit_support

    records = parse_island_visit_support(
        """
        <section>
          <h2>2026 섬 여행비 지원 혜택</h2>
          <dl>
            <dt>지원 대상</dt><dd>성인 누구나</dd>
            <dt>지원 조건</dt><dd>배를 타고 들어가는 섬에서 1박 2일 이상 체류</dd>
            <dt>지원 내용 및 금액</dt><dd>여행비 10만원</dd>
          </dl>
          <p>신청 기간: 2026. 09. 01 ~ 2026. 09. 21</p>
          <p>2026년 10월 1일 ~ 11월 4일 중 섬 여행하기</p>
          <a href="/eligible-islands">대상 섬 목록</a>
        </section>
        """,
        fetched_at=datetime(2026, 9, 13, tzinfo=UTC),
        today=date(2026, 9, 13),
    )

    assert len(records) == 1
    record = records[0]
    assert record.source_category == "island_visit"
    assert record.canonical_key == "2026-island-visit-support"
    assert record.status == "scheduled"
    assert record.extracted_amount_krw == 100_000
    assert record.is_nationwide is True


def test_parse_island_visit_support_raises_when_required_fields_disappear() -> None:
    from app.services.island_visit_parser import (
        IslandVisitParserChangedError,
        parse_island_visit_support,
    )

    with pytest.raises(IslandVisitParserChangedError):
        parse_island_visit_support(
            "<main><h1>프로모션</h1><p>새로운 안내</p></main>",
            fetched_at=datetime(2026, 9, 13, tzinfo=UTC),
            today=date(2026, 9, 13),
        )
