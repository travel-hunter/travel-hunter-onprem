"""여행가는 달 교통 혜택 11건의 상세 문구.

공식 페이지(traffic.do) 본문을 사람이 정리한 표다. 계획: docs/superpowers/plans/2026-09-22-national-policy-detail-copy.md

기간·공식 URL·카드 문구는 수집 때 파서가 주므로 여기에 적지 않는다. 표는 문장만 갖는다.
예외는 114 한 건으로, 페이지 본문이 한 줄뿐이라 공식 캠페인 사이트에서 확인한 내용을
고정 텍스트로 넣고 출처·확인일을 비고에 병기한다.

키는 core_traffic_title() 결과다. 페이지가 제목을 바꾸면 그 카드는 표에서 빠져
일반 경로(혜택 원문 + 기간)로 떨어진다 - tests/test_travelmonth_traffic_detail.py 가 잡는다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.models import ExternalSourceRecord
from app.services.policy_periods import evidence_from_payload, structured_period_items
from app.services.travelmonth_traffic_parser import core_traffic_title


StructuredDetail = dict[str, list[dict[str, Any]]]

SECTION_KEYS = ("supportContent", "periods", "applicationTarget", "requiredDocuments", "notes")


def _items(title: str, *descriptions: str) -> list[dict[str, Any]]:
    """같은 소제목 아래 여러 줄. 프런트는 title 이 같은 항목들을 한 섹션으로 묶는다.
    amount 는 넣지 않는다 - 프런트에서 amount 가 description 을 덮는다."""
    return [{"title": title, "description": description} for description in descriptions]


# 행정안전부 고시 제2021-66호(2021-10-18) 인구감소지역 89곳.
# 군위군은 2023-07-01 대구 편입에 따라 대구로 둔다.
DEPOPULATION_REGIONS: tuple[tuple[str, str], ...] = (
    ("부산", "동구 · 서구 · 영도구"),
    ("대구", "남구 · 서구 · 군위군"),
    ("인천", "강화군 · 옹진군"),
    ("경기", "가평군 · 연천군"),
    ("강원", "고성 · 삼척 · 양구 · 양양 · 영월 · 정선 · 철원 · 태백 · 평창 · 홍천 · 화천 · 횡성"),
    ("충북", "괴산 · 단양 · 보은 · 영동 · 옥천 · 제천"),
    ("충남", "공주 · 금산 · 논산 · 보령 · 부여 · 서천 · 예산 · 청양 · 태안"),
    ("전북", "고창 · 김제 · 남원 · 무주 · 부안 · 순창 · 임실 · 장수 · 정읍 · 진안"),
    (
        "전남",
        "강진 · 고흥 · 곡성 · 구례 · 담양 · 보성 · 신안 · 영광 · 영암 · 완도 · 장성 · 장흥 · 진도 · 함평 · 해남 · 화순",
    ),
    (
        "경북",
        "고령 · 문경 · 봉화 · 상주 · 성주 · 안동 · 영덕 · 영양 · 영주 · 영천 · 울릉 · 울진 · 의성 · 청도 · 청송",
    ),
    ("경남", "거창 · 고성 · 남해 · 밀양 · 산청 · 의령 · 창녕 · 하동 · 함안 · 함양 · 합천"),
)

_DEPOPULATION_TITLE = "대상 지역 (인구감소지역 89곳)"
_DEPOPULATION_SOURCE_NOTE = "인구감소지역 목록: 행정안전부 고시(2021-10-18) 기준, 2026-09-22 확인."


_DEPOPULATION_LIST_URL = "https://korean.visitkorea.or.kr/travelmonth/benefits/depopulation.do"


def depopulation_region_count(names: str) -> int:
    return len(names.split(" · "))


def _depopulation_region_items() -> list[dict[str, Any]]:
    """89곳을 다 적으면 상세가 지명 목록에 묻힌다. 시·도별 개수만 한 줄로 보여 주고
    시·군·구 목록은 공식 안내로 넘긴다."""
    summary = " · ".join(
        f"{province} {depopulation_region_count(names)}" for province, names in DEPOPULATION_REGIONS
    )
    return [
        {"title": _DEPOPULATION_TITLE, "description": summary},
        {
            "title": _DEPOPULATION_TITLE,
            "description": "해당 시 · 군 · 구 전체 목록은 여행가는 달 인구감소지역 안내에서 확인할 수 있습니다.",
            "url": _DEPOPULATION_LIST_URL,
        },
    ]


# 109·110 은 같은 네이버 항공권 프로모션이다. 110 은 본문이 한 줄뿐이라 109 의 노선·지급액을 함께 쓴다.
_NAVER_POINT_ROUTES = _items(
    "지급 포인트",
    "내륙노선: 항공권 구매·이용 시 1인 1만 포인트, 왕복 기준 최대 4만 포인트",
    "제주노선: 항공권 구매·이용 시 1인 5천 포인트, 왕복 기준 최대 2만 포인트",
) + _items(
    "대상 노선",
    "내륙 - 김포 ↔ 광주 · 울산 · 여수 · 포항/경주 · 사천",
    "제주 - 제주 ↔ 김해 · 청주 · 대구 · 양양 · 광주 · 울산 · 여수 · 포항/경주 · 사천 · 군산 · 원주",
)
_NAVER_POINT_NOTES = _items(
    "비고",
    "상황에 따라 대상 노선이 변동될 수 있습니다.",
    "예산 소진 시 조기 마감될 수 있습니다.",
)

# 111·112 는 같은 티맵 인구감소지역 주행 혜택이다. 112 는 소개 카드라 111 의 내용을 함께 쓴다.
_TMAP_DRIVE_SUPPORT = (
    _items(
        "지원 내용",
        "인구감소지역(89개) 소재 관광지를 목적지로 출발지 기준 30km 이상 주행하면 스탬프와 티맵 포인트를 받습니다. 한 계정당 최대 3만 포인트(누적)입니다.",
    )
    + _items(
        "받는 방법",
        "① 티맵에서 인구감소지역 관광지(목적지) 검색",
        "② 방문",
        "③ 스탬프 적립",
        "④ 스탬프 개수 기반 티맵 포인트 지급",
    )
    + _items(
        "지급 기준",
        "① 첫 번째 스탬프 적립 시 5천 포인트",
        "② 두 번째 스탬프 적립 시 1만 포인트",
        "③ 세 번째 스탬프 적립 시 1.5만 포인트",
    )
    + _items(
        "추가 혜택",
        "① 전기차 운전자에게 티맵 포인트 2천원 지급",
        "② 인구감소지역 방문 후 공사 디지털 관광 주민증 사용 시 티맵 포인트 5천원 지급",
        "③ 티맵 영상 리뷰 작성 시 티맵 포인트 2천원 지급",
    )
    + _depopulation_region_items()
)
_TMAP_DRIVE_TARGET = _items(
    "참여 조건",
    "친환경 · 안전운전 여행 서약",
    "출발지 기준 30km 이상 주행하여 인구감소지역 내 관광지를 목적지로 방문 (본인 거주지역 제외)",
    "방문 지역(기초)당 스탬프가 쌓이며 같은 지역 중복은 인정되지 않습니다.",
)
_TMAP_DRIVE_NOTES = _items(
    "비고",
    "본 프로모션은 티맵 모바일 앱에서만 확인 가능합니다.",
    "혜택별 운영 기간은 변동될 수 있습니다.",
    "예산 소진 시 조기 마감될 수 있습니다.",
    _DEPOPULATION_SOURCE_NOTE,
)

# 113·114 는 같은 카모아 렌터카 쿠폰을 서로 다른 캠페인에서 안내한다.
_CARMORE_CROSS_NOTE = (
    "같은 카모아 렌터카 쿠폰이 여행가는 달(연안지역 렌터카 할인)과 바다가는 달 양쪽에서 안내됩니다. "
    "중복 발급은 불가할 수 있습니다."
)


TRAFFIC_DETAIL_BY_TITLE: dict[str, StructuredDetail] = {
    "인구감소지역 자유여행상품 할인": {
        "supportContent": _items(
            "지원 내용",
            "인구감소지역 자유여행상품을 구매하고 그 지역 관광지 방문을 인증하면 구매한 승차권 운임의 100% 상당 철도 할인쿠폰을 받습니다.",
        )
        + _items(
            "받는 방법",
            "① 인구감소지역 자유여행상품 구매",
            "② 인구감소지역 소재 관광지 방문 인증 (코레일톡 QR코드 또는 디지털관광주민증)",
            "③ 열차 할인쿠폰 지급",
        )
        + _depopulation_region_items(),
        "periods": [],
        "applicationTarget": _items("신청 대상", "인구감소지역 자유여행상품 구매자"),
        "requiredDocuments": [],
        "notes": _items(
            "비고",
            "방문을 인증한 뒤에 받는 할인쿠폰입니다. 출발 전 무료 승차가 아니라 다음 열차 예매에 쓰는 할인입니다.",
            "11월 28일 출발 상품까지만 예약할 수 있습니다.",
            _DEPOPULATION_SOURCE_NOTE,
        ),
    },
    "인구감소지역 자유여행상품 추가 혜택": {
        "supportContent": _items(
            "지원 내용",
            "13개 인구감소지역 자유여행상품 구매자에게 디지털 온누리상품권을 1인당 2만원씩 선착순 지급합니다.",
        )
        + _items(
            "대상 지역 (13곳)",
            "해남군 · 함평군 · 장성군 · 태백시 · 보성군 · 임실군 · 강진군 · 군위군 · 괴산군 · 봉화군 · 장흥군 · 의성군 · 무주군",
        ),
        "periods": [],
        "applicationTarget": _items(
            "신청 대상",
            "위 13개 지역 자유여행상품 구매자",
            "선착순 지급 (1인당 2만원)",
        ),
        "requiredDocuments": [],
        "notes": _items(
            "비고",
            "이 혜택의 대상 지역은 13곳으로, 인구감소지역 89곳 전체를 대상으로 하는 철도 할인쿠폰 · 자동차 여행 할인과 범위가 다릅니다.",
        ),
    },
    "테마열차 할인": {
        "supportContent": _items("지원 내용", "5개 정기노선 테마열차의 운임료를 50% 할인합니다.")
        + _items(
            "대상 열차",
            "동해산타열차",
            "남도해양(전라 · 경전)열차",
            "정선아리랑열차",
            "서해금빛열차",
            "백두대간협곡열차",
        ),
        "periods": [],
        "applicationTarget": [],
        "requiredDocuments": [],
        "notes": _items("비고", "운행 일정과 예매 방법은 공식 페이지에서 확인하세요."),
    },
    "내일로패스 할인": {
        "supportContent": _items("지원 내용", "내일로패스 탑승권을 2만원 정액 할인합니다.")
        + _items(
            "대상 열차",
            "KTX 및 일반열차 (ITX-마음, ITX-청춘, ITX-새마을, 새마을, 무궁화, 누리로)",
        ),
        "periods": [],
        "applicationTarget": [],
        "requiredDocuments": [],
        "notes": _items(
            "비고",
            "11월 24일에 이용을 시작하는 패스까지만 예약할 수 있습니다.",
            "예산 소진 시 조기 마감될 수 있습니다.",
        ),
    },
    "자유로운 기차여행": {
        "supportContent": _items(
            "지원 내용",
            "여행가는 달 기간의 철도 혜택 네 가지를 한 번에 안내하는 카드입니다. 각 혜택은 따로 신청합니다.",
        )
        + _items(
            "포함 혜택",
            "철도 할인쿠폰 - 구매 승차권 운임의 100% 상당",
            "디지털 온누리상품권 - 선착순 1인당 2만원권 지급",
            "테마열차 - 운임 50% 할인",
            "내일로패스 - 2만원 할인",
        ),
        "periods": [],
        "applicationTarget": [],
        "requiredDocuments": [],
        "notes": _items("비고", "각 혜택의 대상과 조건은 해당 혜택 카드에서 확인하세요."),
    },
    "네이버 페이 N포인트 지급 (최대 4만 포인트)": {
        "supportContent": _items(
            "지원 내용",
            "네이버 항공권에서 대상 국내선 항공권을 구매하고 이용하면 네이버페이 N포인트를 받습니다.",
        )
        + _NAVER_POINT_ROUTES,
        "periods": [],
        "applicationTarget": [],
        "requiredDocuments": [],
        "notes": _NAVER_POINT_NOTES,
    },
    "방방곡곡 국내 여행": {
        "supportContent": _items(
            "지원 내용",
            "네이버 항공권에서 대상 국내선 항공권을 구매하고 이용하면 네이버페이 N포인트를 받습니다.",
        )
        + _NAVER_POINT_ROUTES,
        "periods": [],
        "applicationTarget": [],
        "requiredDocuments": [],
        "notes": _NAVER_POINT_NOTES
        + _items("비고", "네이버 항공권 N포인트 지급 혜택과 같은 프로모션입니다."),
    },
    "인구감소지역 자동차 여행 할인": {
        "supportContent": _TMAP_DRIVE_SUPPORT,
        "periods": [],
        "applicationTarget": _TMAP_DRIVE_TARGET,
        "requiredDocuments": [],
        "notes": _TMAP_DRIVE_NOTES,
    },
    "모두를 지키는 안전운전": {
        "supportContent": _TMAP_DRIVE_SUPPORT,
        # 레코드에 기간이 없다. 같은 프로그램인 인구감소지역 자동차 여행 할인의 기간을 표시용으로 적는다.
        "periods": [
            {
                "title": "이용 기간",
                "description": "10월 1일 ~ 11월 30일 (인구감소지역 자동차 여행 할인과 같은 기간)",
                "type": "usage",
                "startDate": "2026-10-01",
                "endDate": "2026-11-30",
            }
        ],
        "applicationTarget": _TMAP_DRIVE_TARGET,
        "requiredDocuments": [],
        "notes": _items(
            "비고",
            "인구감소지역 자동차 여행 할인과 같은 티맵 혜택을 소개하는 카드입니다.",
            "티맵 바로가기는 2026년 10월 1일 오픈 예정입니다.",
        )
        + _TMAP_DRIVE_NOTES,
    },
    "연안지역 제약환경(교통) 개선 및 체류 확대를 위한 렌터카 할인": {
        "supportContent": _items(
            "지원 내용",
            "연안지역 기초 지자체 여행상품 구매자에게 저공해 렌터카 할인쿠폰을 제공합니다. 대여 시간과 지역에 따라 최대 2만원입니다.",
        )
        + _items(
            "할인 금액",
            "제주도 외 연안지역 기초 지자체 - 24시간 1만원 / 48시간 2만원",
            "제주도 - 24시간 최대 5천원 / 48시간 최대 1만원",
        )
        + _items(
            "대상 지역",
            "강원 · 충남 · 전북 · 전남 · 광주 · 경북 · 부산 · 울산 · 경남 · 제주 안의 연안지역 기초 지자체",
            "해당 시 / 군 / 구 목록은 공식 사이트에서 확인할 수 있습니다.",
        )
        + _items("대상 차량", "저공해 렌터카 - 하이브리드차, 전기차, LPG 차량"),
        "periods": [],
        "applicationTarget": _items(
            "신청 조건",
            "온라인 예약 및 결제 건에만 적용됩니다. 오프라인 현장 결제 건은 적용되지 않습니다.",
            "1인 1매로 제한되며, 예산 소진 시 조기 마감될 수 있습니다.",
        ),
        "requiredDocuments": [],
        "notes": _items(
            "비고",
            "차량 이용에 수반되는 보험료와 유류비에는 할인쿠폰이 적용되지 않습니다.",
            _CARMORE_CROSS_NOTE,
        ),
    },
    "바다가는 달": {
        "supportContent": _items(
            "지원 내용",
            "한국관광공사와 카모아가 함께 제공하는 친환경 렌터카 할인쿠폰입니다. 최대 2만원권을 받을 수 있습니다.",
        )
        + _items("대상 지역", "수도권을 제외한 연안 64개 시 · 군 · 구"),
        # 레코드에 기간이 없다. 공식 캠페인 사이트에서 확인한 기간을 표시용으로 적는다.
        "periods": [
            {
                "title": "쿠폰 발급 기간",
                "description": "9월 15일 ~ 10월 31일",
                "type": "issue",
                "startDate": "2026-09-15",
                "endDate": "2026-10-31",
            },
            {
                "title": "탑승 기간",
                "description": "10월 1일 ~ 10월 31일 (예정)",
                "type": "usage",
                "startDate": "2026-10-01",
                "endDate": "2026-10-31",
            },
        ],
        "applicationTarget": _items("신청 조건", "친환경 차량을 24시간 이상 대여하는 경우"),
        "requiredDocuments": [],
        "notes": _items(
            "비고",
            "쿠폰 발급 기간 · 탑승 기간 · 대상 지역은 공식 캠페인 사이트(https://seatravelmonth.kr/event/) 2026-09-22 확인 기준입니다.",
            _CARMORE_CROSS_NOTE,
        ),
    },
}


def _date_text(value: object) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _korean_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        return value
    return f"{parsed.month}월 {parsed.day}일"


def _record_date_period(record: ExternalSourceRecord) -> list[dict[str, Any]]:
    """근거 문장 없이 날짜만 있는 레코드(인구감소지역 자동차 여행 할인)를 위한 최소 기간 항목."""
    start, end = _date_text(record.start_date), _date_text(record.end_date)
    if not start and not end:
        return []
    # 다른 카드의 기간은 페이지 원문("10월 1일 ~ 11월 30일")이다. 형식을 맞춘다.
    description = " ~ ".join(v for v in (_korean_date(start), _korean_date(end)) if v)
    item: dict[str, Any] = {"title": "기간", "description": description}
    if start:
        item["startDate"] = start
    if end:
        item["endDate"] = end
    return [item]


def _parsed_period_items(record: ExternalSourceRecord) -> list[dict[str, Any]]:
    # 기간이 없는 레코드도 있다(11건 중 6건). 연도는 원문에 연도가 없을 때만 쓰인다.
    reference = record.start_date or record.last_fetched_at or record.created_at
    # sqlite 백엔드는 날짜를 문자열로 돌려준다 - year 가 없으면 올해로 둔다.
    default_year = getattr(reference, "year", None) or date.today().year
    evidence = evidence_from_payload(
        record.raw_payload,
        default_year=default_year,
        source=record.source_category or "traffic_benefit",
    )
    return structured_period_items(evidence)


def structured_detail_for_traffic(record: ExternalSourceRecord) -> StructuredDetail:
    """표의 문장 + 수집 때 파싱된 기간. 표에 없는 제목은 혜택 원문으로 떨어진다."""
    curated = TRAFFIC_DETAIL_BY_TITLE.get(core_traffic_title(record.title or ""))
    detail: StructuredDetail = {
        key: [dict(item) for item in (curated or {}).get(key, [])] for key in SECTION_KEYS
    }
    if curated is None:
        benefit_text = " ".join(str(record.benefit_text or "").split())
        if benefit_text:
            detail["supportContent"] = _items("혜택", benefit_text)

    # 파싱된 기간이 있으면 그것이 최신이다. 표의 기간은 레코드에 기간이 없을 때만 쓴다.
    parsed_periods = _parsed_period_items(record)
    if parsed_periods:
        detail["periods"] = parsed_periods
    elif not detail["periods"]:
        detail["periods"] = _record_date_period(record)
    return detail
