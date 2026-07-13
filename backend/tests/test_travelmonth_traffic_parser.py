from __future__ import annotations

from datetime import UTC, date, datetime

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
