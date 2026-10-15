"""정책 링크는 국가 · 공공기관이 직접 운영하는 사이트로만(2026-10-15 사용자 결정).

민간 운영사(네이버 · 티맵 · 카모아) 행사와 '여행가는 달' 같은 홍보 페이지는 링크를 걸지 않는다 -
정책과 혜택 내용은 남기고 바깥 링크 단추만 없앤다.
"""

from __future__ import annotations

import pytest

from app.services.policy_normalization import _official_url_for_external_record
from tests.test_policy_candidate_review import make_record

TRAVEL_MONTH_TRAFFIC = "https://korean.visitkorea.or.kr/travelmonth/benefits/traffic.do"


def _record(detail_url: str | None, collected_page_url: str = TRAVEL_MONTH_TRAFFIC):
    record = make_record()
    record.source_category = "traffic_benefit"
    record.detail_url = detail_url
    record.collected_page_url = collected_page_url
    return record


@pytest.mark.parametrize(
    "url",
    [
        "https://travel.naver.co.kr/koreatravel",
        "https://tmap.life/64246a7d",
        "https://carmore.kr/home/page-event-detail.html?a=529",
        TRAVEL_MONTH_TRAFFIC,
        "https://korean.visitkorea.or.kr/travelmonth/main.do",
    ],
)
def test_private_operators_and_the_travel_month_page_get_no_link(url: str) -> None:
    assert _official_url_for_external_record(_record(url)) is None


def test_no_link_does_not_fall_back_to_the_travel_month_page() -> None:
    assert _official_url_for_external_record(_record(None)) is None


@pytest.mark.parametrize(
    "url",
    [
        "https://www.korail.com/tour/touristIntor/tourEvent/monthTour",
        "https://seatravelmonth.kr/event/",
        "https://taeantour.kr",
        "https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
    ],
)
def test_public_sites_keep_their_link(url: str) -> None:
    assert _official_url_for_external_record(_record(url)) == url
