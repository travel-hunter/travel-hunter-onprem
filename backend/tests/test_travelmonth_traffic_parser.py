from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.services.travelmonth_traffic_parser import parse_traffic_benefits

TRAFFIC_HTML = """
<html><body>
<h3>여행가는 달 철도 할인 프로모션</h3>
<h4>테마열차 할인</h4>
<p>5개 정기노선 운임료 50% 할인</p>
<dl>
  <dt>판매 기간</dt><dd>2026.03.16 ~ 2026.05.31</dd>
  <dt>이용 기간</dt><dd>2026.04.01 ~ 2026.05.31</dd>
  <dt>문의처</dt><dd>한국철도공사 고객센터(1544-7788)</dd>
</dl>
<a href="https://www.korail.com">할인혜택 보러가기</a>
<h3>여행가는 달 국내 항공권 할인 프로모션</h3>
<h4>네이버 항공권에서 국내선 이용 시</h4>
<p>항공권 발권 인당 5천 포인트 지급 (최대 2만 포인트)</p>
<dl>
  <dt>판매 기간</dt><dd>2026.03.16 ~ 2026.05.31</dd>
  <dt>이용 기간</dt><dd>2026.04.01 ~ 2026.05.31</dd>
  <dt>문의처</dt><dd>네이버 항공권</dd>
</dl>
<a href="https://travel.naver.co.kr/koreatravel">할인혜택 보러가기</a>
</body></html>
"""


def test_parse_traffic_benefits_extracts_rail_and_air_records() -> None:
    records = parse_traffic_benefits(
        TRAFFIC_HTML,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        fetched_at=datetime(2026, 5, 23, tzinfo=UTC),
        today=date(2026, 5, 23),
    )

    assert [record.source_category for record in records] == [
        "traffic_benefit",
        "traffic_benefit",
    ]
    assert records[0].title == "테마열차 할인"
    assert records[0].organizer_text == "한국철도공사"
    assert records[0].region == "전국"
    assert records[0].is_nationwide is True
    assert records[0].status == "active"
    assert records[0].extracted_discount_percent == 50
    assert records[0].detail_url == "https://www.korail.com"
    assert records[1].title == "네이버 항공권에서 국내선 이용 시"
    assert records[1].organizer_text == "네이버 항공권"
    assert records[1].extracted_amount_krw == 20000
    assert records[1].benefit_value_text == "최대 2만 포인트"


def test_air_summary_uses_qualified_maximum_and_excludes_page_chrome() -> None:
    html = (
        Path(__file__).parent / "fixtures" / "traffic_card_quality.html"
    ).read_text(encoding="utf-8")

    rows = parse_traffic_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        fetched_at=datetime(2026, 9, 21, tzinfo=UTC),
        today=date(2026, 9, 21),
    )

    assert len(rows) == 1
    air = rows[0]
    assert air.title == "네이버 항공권 국내선 포인트"
    assert air.raw_payload["cardCopy"]["summary"] == "왕복 기준, 최대 4만 포인트"
    assert "Copyright" not in air.benefit_text
    assert "99만원" not in air.benefit_text
    assert air.start_date == date(2026, 9, 15)
    assert air.end_date == date(2026, 11, 30)
    assert all(row.benefit_text != "할인혜택 보러가기" for row in rows)


def test_unqualified_maximum_is_held_for_review() -> None:
    html = """
    <html><body>
      <h3>교통 포인트 이벤트</h3>
      <h4>국내선 포인트</h4>
      <p>항공권 구매 시 인당 1만 포인트 지급</p>
      <ul><li>이벤트 최대 4만 포인트 지급</li></ul>
    </body></html>
    """

    rows = parse_traffic_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        fetched_at=datetime(2026, 9, 21, tzinfo=UTC),
        today=date(2026, 9, 21),
    )

    assert len(rows) == 1
    assert rows[0].benefit_value_text == "최대 4만 포인트"
    assert rows[0].raw_payload["cardCopy"]["summary"] is None
    assert "benefit_unit_ambiguous" in rows[0].raw_payload["cardCopy"]["issues"]


@pytest.mark.parametrize(
    ("benefit_text", "expected_summary"),
    [
        ("5개 정기노선 운임료 50% 할인", "운임료 50% 할인"),
        ("철도 할인쿠폰 제공 구매 승차권 운임의 100% 상당", "승차권 운임 100% 상당 쿠폰"),
        ("디지털 온누리상품권 선착순 지급(1인당 2만원)", "1인당 2만원 상품권"),
        ("KTX 탑승권 2만원 정액 할인", "2만원 정액 할인"),
        ("항공권 발권 인당 5천 포인트 지급", "인당 5천 포인트"),
    ],
)
def test_traffic_card_summary_preserves_source_specific_benefit_unit(
    benefit_text: str, expected_summary: str
) -> None:
    html = f"<html><body><h4>교통 혜택</h4><p>{benefit_text}</p></body></html>"

    rows = parse_traffic_benefits(
        html,
        collected_page_url="https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do",
        fetched_at=datetime(2026, 9, 21, tzinfo=UTC),
        today=date(2026, 9, 21),
    )

    assert len(rows) == 1
    assert rows[0].raw_payload["cardCopy"]["summary"] == expected_summary
    assert rows[0].raw_payload["cardCopy"]["issues"] == []
