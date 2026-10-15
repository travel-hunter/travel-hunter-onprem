from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.services.travelmonth_normalizer import normalize_text
from app.services.travelmonth_traffic_parser import SOURCE_URL, parse_traffic_benefits, traffic_canonical_key

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
    assert air.raw_payload["cardCopy"]["summary"] == "대상 국내선 왕복 최대 4만 포인트"
    assert "Copyright" not in air.benefit_text
    assert "99만원" not in air.benefit_text
    assert air.start_date == date(2026, 9, 15)
    assert air.end_date == date(2026, 11, 30)
    assert all(row.benefit_text != "할인혜택 보러가기" for row in rows)


def test_unqualified_maximum_uses_the_largest_point_value() -> None:
    # 예전에는 "왕복 기준" 같은 자격이 없는 최대값을 보류했다. 이제는 제목/본문의 가장 큰 값을 쓴다 -
    # 카드에는 대상과 최대 혜택만 있으면 되고, 조건은 상세가 보여 준다.
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
    assert rows[0].raw_payload["cardCopy"]["summary"] == "국내선 최대 4만 포인트"
    assert rows[0].raw_payload["cardCopy"]["issues"] == []


@pytest.mark.parametrize(
    ("benefit_text", "expected_summary"),
    [
        ("5개 정기노선 운임료 50% 할인", "운임 50% 할인"),
        ("철도 할인쿠폰 제공 구매 승차권 운임의 100% 상당", "철도 운임 100% 할인쿠폰"),
        ("디지털 온누리상품권 선착순 지급(1인당 2만원)", "온누리상품권 2만원"),
        ("KTX 탑승권 2만원 정액 할인", "철도 2만원 할인"),
        ("항공권 발권 인당 5천 포인트 지급", "국내선 최대 5천 포인트"),
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


# --- 2026-09-22 라이브 페이지: 전국 교통 12건의 카드 문구·지원내용 목표 ---------------------------
# 표는 docs/superpowers/plans/2026-09-22-national-policy-card-display.md Task 1-B 와 같다.
# 카드 문구 = "대상 + 혜택" 한 구절, 지원내용 = 그 카드 블록의 첫 문단만(검색어·푸터·다음 카드 없음).

LIVE_FIXTURE = Path(__file__).parent / "fixtures" / "traffic_benefits_2026-09-22.html"

NATIONAL_CARD_EXPECTATIONS = [
    ("인구감소지역 자유여행상품 할인", "방문 인증 운임 쿠폰·온누리 2만원", "인구감소지역 자유여행상품 * 구매자 대상 철도 할인쿠폰 제공"),
    ("테마열차 할인", "테마열차 운임 50% 할인", "5개 정기노선 * 운임료 50% 할인"),
    ("내일로패스 할인", "내일로패스 2만원 할인", "내일로패스 KTX 및 일반열차 * 탑승권 2만원 정액 할인"),
    ("대한민국 구석구석 자유로운 기차여행", "철도 할인쿠폰·테마열차·내일로 혜택", "철도 할인쿠폰 제공 구매 승차권 운임의 100%"),
    ("’네이버 항공권‘에서 국내선 이용 시 네이버 페이 N포인트 지급 (최대 4만 포인트)", "대상 국내선 왕복 최대 4만 포인트", "(내륙노선) 항공권 구매 · 이용 시 인당 1만 포인트"),
    ("비행기타고 떠나는 방방곡곡 국내 여행", "대상 국내선 왕복 최대 4만 포인트", "네이버 항공권에서 국내선 이용 시 최대 4만 포인트 지급"),
    ("인구감소지역 자동차 여행 할인", "티맵 방문 스탬프 누적 최대 3만 포인트", "인구감소지역(89개) 소재 관광지를 목적지로 출발지 기준 30km 이상 주행한 경우"),
    ("지구를 지키는 친환경여행 모두를 지키는 안전운전", "최대 3만 포인트", "인구감소지역 방문 주행 시 최대 3만 포인트 지급"),
    ("연안지역 제약환경(교통) 개선 및 체류 확대를 위한 렌터카 할인", "저공해 렌터카 최대 2만원 할인쿠폰", "연안지역 기초 지자체 상품 구매자 대상 저공해 렌터카 * 할인쿠폰 제공"),
    ("바다가는 달", "카모아 렌터카 최대 2만원 쿠폰", "카모아 렌터카 최대 2만원 권 제공"),
]

# 어떤 카드의 지원내용에도 들어오면 안 되는 사이트 잔여물
SITE_CHROME = ("인기 검색어", "한국관광공사 :", "Copyright", "통신판매업신고", "추천 검색어", "할인혜택 보러가기")


def _live_rows():
    html = LIVE_FIXTURE.read_text(encoding="utf-8", errors="replace")
    return {
        row.title: row
        for row in parse_traffic_benefits(
            html,
            collected_page_url=SOURCE_URL,
            fetched_at=datetime(2026, 9, 22, 9, 0, 0),
            today=date(2026, 9, 22),
        )
    }


@pytest.mark.parametrize(("title", "card", "detail_prefix"), NATIONAL_CARD_EXPECTATIONS)
def test_live_national_cards_get_target_plus_benefit_copy(title: str, card: str, detail_prefix: str) -> None:
    rows = _live_rows()
    assert title in rows, sorted(rows)
    row = rows[title]
    card_copy = (row.raw_payload or {}).get("cardCopy", {})

    assert card_copy.get("summary") == card
    assert len(card_copy.get("summary") or "") <= 40
    assert card_copy.get("issues") == []
    assert normalize_text(row.benefit_text).startswith(normalize_text(detail_prefix))
    for chrome in SITE_CHROME:
        assert chrome not in (row.raw_detail_text or ""), (title, chrome)
        assert chrome not in (row.benefit_text or ""), (title, chrome)


def test_live_page_yields_the_ten_traffic_cards() -> None:
    # 자유여행상품 추가 혜택은 할인 카드에 합쳐져 11 → 10(2026-10-15 사용자 결정)
    rows = _live_rows()
    assert len(rows) == 10
    # 다음 카드 제목이 앞 카드 원문에 딸려 들어오지 않는다
    titles = list(rows)
    for earlier, later in zip(titles, titles[1:]):
        assert later not in (rows[earlier].raw_detail_text or ""), (earlier, later)


# --- canonical_key: 원문이 바뀌어도 같은 정책이어야 한다 -------------------------------------------


def _one(html_benefit: str, title: str = "테마열차 할인"):
    html = f"<html><body><article><div><h4>{title}</h4><p>{html_benefit}</p></div></article></body></html>"
    rows = parse_traffic_benefits(
        html, collected_page_url=SOURCE_URL, fetched_at=datetime(2026, 9, 22, tzinfo=UTC), today=date(2026, 9, 22)
    )
    assert len(rows) == 1
    return rows[0]


def test_canonical_key_follows_the_title_not_the_benefit_text() -> None:
    # 원문이 다듬어지거나 기간이 바뀌어도 같은 정책이다 - 예전에는 원문 해시라 재수집마다 정책이 복제됐다
    a = _one("5개 정기노선 운임료 50% 할인")
    b = _one("5개 정기노선 * 운임료 50% 할인 동해산타열차 외 (2026.10.1~11.30)")
    assert a.canonical_key == b.canonical_key == traffic_canonical_key("테마열차 할인")
    assert a.external_id == a.canonical_key


@pytest.mark.parametrize(
    ("page_title", "core_title"),
    [
        ("대한민국 구석구석 자유로운 기차여행", "자유로운 기차여행"),
        ("비행기타고 떠나는 방방곡곡 국내 여행", "방방곡곡 국내 여행"),
        ("지구를 지키는 친환경여행 모두를 지키는 안전운전", "모두를 지키는 안전운전"),
        ("’네이버 항공권‘에서 국내선 이용 시 네이버 페이 N포인트 지급 (최대 4만 포인트)", "네이버 페이 N포인트 지급 (최대 4만 포인트)"),
        ("테마열차  할인", "테마열차 할인"),
    ],
)
def test_canonical_key_ignores_campaign_prefixes_and_quotes(page_title: str, core_title: str) -> None:
    # 페이지가 제목 앞에 캠페인 문구를 붙였다 뗐다 한다 - 핵심 명칭만으로 같은 정책이어야 한다
    assert traffic_canonical_key(page_title) == traffic_canonical_key(core_title)


def test_different_policies_still_get_different_keys() -> None:
    assert traffic_canonical_key("테마열차 할인") != traffic_canonical_key("내일로패스 할인")

def test_air_card_does_not_infer_four_person_cap_without_page_evidence() -> None:
    html = """
    <html><body><h4>네이버 항공권 국내선 포인트</h4>
    <p>국내선 이용 시 최대 4만 포인트 지급</p></body></html>
    """
    rows = parse_traffic_benefits(
        html,
        collected_page_url=SOURCE_URL,
        fetched_at=datetime(2026, 9, 22, tzinfo=UTC),
        today=date(2026, 9, 22),
    )

    assert rows[0].raw_payload["cardCopy"]["summary"] == "국내선 최대 4만 포인트"


# --- 바로가기: 홍보 페이지가 아니라 혜택을 실제로 받는 곳으로 -----------------------------------------

KORAIL_MONTH = "https://www.korail.com/tour/touristIntor/tourEvent/monthMain"
KORAIL_FREE_TOUR = "https://www.korail.com/tour/touristIntor/tourEvent/monthTour"
KORAIL_THEME_TRAIN = "https://www.korail.com/tour/touristIntor/tourEvent/monthTourSale"


@pytest.mark.parametrize(
    ("title", "url"),
    [
        ("인구감소지역 자유여행상품 할인", KORAIL_FREE_TOUR),
        ("테마열차 할인", KORAIL_THEME_TRAIN),
        ("연안지역 제약환경(교통) 개선 및 체류 확대를 위한 렌터카 할인", "https://seatravelmonth.kr/event/"),
    ],
)
def test_cards_without_a_link_on_the_page_go_to_the_benefit_site(title: str, url: str) -> None:
    # 여행가는 달 페이지에 바로가기가 없는 카드 - 국가 · 공공 운영 혜택 화면으로(2026-10-14 확인, 민간 운영사는 표에 넣지 않는다)
    row = _live_rows()[title]
    assert row.detail_url == url


def test_a_link_on_the_page_wins_over_the_known_link() -> None:
    html = (
        "<html><body><article><div><h4>테마열차 할인</h4><p>5개 정기노선 운임료 50% 할인</p>"
        '<a href="https://www.korail.com/new-theme">할인혜택 보러가기</a></div></article></body></html>'
    )
    rows = parse_traffic_benefits(
        html, collected_page_url=SOURCE_URL, fetched_at=datetime(2026, 9, 22, tzinfo=UTC), today=date(2026, 9, 22)
    )
    assert rows[0].detail_url == "https://www.korail.com/new-theme"


# --- 포인트 금액: '1.5만' 을 '5만' 으로 읽지 않는다 -------------------------------------------------


def test_decimal_points_are_not_read_as_their_last_digit() -> None:
    # 실페이지: 스탬프 1.5만 포인트 · 계정당 최대 3만 - 예전에는 '1.5만' 의 '5만' 을 잡아 최대 5만으로 보였다
    rows = _live_rows()
    assert rows["인구감소지역 자동차 여행 할인"].benefit_value_text == "최대 3만 포인트"
    assert rows["인구감소지역 자동차 여행 할인"].extracted_amount_krw == 30000


def test_a_decimal_maximum_keeps_its_decimal() -> None:
    row = _one("세 번째 스탬프 적립 시 1.5만 포인트 지급")
    assert row.benefit_value_text == "최대 1.5만 포인트"
    assert row.extracted_amount_krw == 15000


def test_tmap_cards_no_longer_say_the_link_opens_later() -> None:
    from app.services.travelmonth_traffic_detail import TRAFFIC_DETAIL_BY_TITLE

    notes = " ".join(item.get("value", "") or item.get("description", "") for item in TRAFFIC_DETAIL_BY_TITLE["모두를 지키는 안전운전"]["notes"])
    assert "오픈 예정" not in notes


# --- 페이지 링크보다 먼저: 페이지가 FAQ · 메인으로 걸어 둔 카드(2026-10-14 사용자 확인) -------------


@pytest.mark.parametrize(
    ("title", "url"),
    [
        ("내일로패스 할인", "https://www.korail.com/tour/freeTravel/railro/passIntro"),
    ],
)
def test_preferred_links_win_over_the_page_link(title: str, url: str) -> None:
    assert _live_rows()[title].detail_url == url


def test_korail_cards_each_go_to_their_own_tab() -> None:
    # 코레일 여행가는 달은 탭마다 주소가 다르다(메인 · 자유 여행 상품 · 테마 열차 할인 · 내일로 패스) - 카드가 서로 겹치지 않는다
    rows = _live_rows()
    assert rows["대한민국 구석구석 자유로운 기차여행"].detail_url == KORAIL_MONTH  # 캠페인 전체 카드 - 페이지 링크 그대로
    korail = ["대한민국 구석구석 자유로운 기차여행", "인구감소지역 자유여행상품 할인", "테마열차 할인", "내일로패스 할인"]
    assert len({rows[title].detail_url for title in korail}) == 4


# --- 자유여행상품 할인 + 추가 혜택은 한 정책 ------------------------------------------------------------


def test_free_tour_add_on_folds_into_the_discount_card() -> None:
    # 같은 상품을 사야 받는 덧붙임 혜택이고 코레일 같은 화면에 있다 - 카드를 따로 세우지 않는다
    rows = _live_rows()
    assert "인구감소지역 자유여행상품 추가 혜택" not in rows
    merged = rows["인구감소지역 자유여행상품 할인"]
    assert "온누리상품권" in merged.benefit_text
    assert "1인당 2만원" in merged.benefit_text
    assert normalize_text(merged.benefit_text).startswith("인구감소지역 자유여행상품 * 구매자 대상 철도 할인쿠폰 제공")
    # 카드 금액은 주된 혜택(운임 100%)에서 읽는다 - 덧붙임의 2만원이 금액이 되지 않는다
    assert merged.benefit_value_text == "최대 100%"
