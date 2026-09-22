from datetime import UTC, date, datetime
from pathlib import Path

import pytest

# Official page saved 2026-09-14 (public). Rounds 1 and 2 are both on the page, mixed with commented-out blocks.
FIXTURE = Path(__file__).parent / "fixtures" / "island_visit_promotion2_2026-09-14.html"


def _fixture_record(today: date = date(2026, 9, 14)):
    from app.services.island_visit_parser import parse_island_visit_support

    return parse_island_visit_support(
        FIXTURE.read_text(encoding="utf-8"),
        fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
        today=today,
    )[0]


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
            <dt>지급 시기</dt><dd>여행 후 2주 이내 서류 제출 필요</dd>
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
    assert record.raw_payload["cardCopy"]["summary"] == record.benefit_value_text
    assert "procedure" in record.raw_payload


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


# --- real official page ---------------------------------------------------------------------


def test_real_page_card_fields_are_values_not_label_fragments() -> None:
    record = _fixture_record()
    assert record.benefit_text.startswith("여행비 10만원")
    assert record.extracted_amount_krw == 100_000
    assert (record.start_date, record.end_date) == (date(2026, 10, 1), date(2026, 11, 4))
    assert "9월 21일" in record.raw_payload["applicationPeriod"]
    assert record.raw_payload["eligibleIslandsUrl"] == "https://buly.kr/8piNoSv"


def test_real_page_procedure_keeps_every_round_with_its_live_forms() -> None:
    procedure = _fixture_record().raw_payload["procedure"]
    assert procedure["rounds"] == [
        {
            "key": "1",
            "applyStart": "2026-06-17T10:00",
            "applyUntil": "2026-06-30T23:59",
            "travelStart": "2026-07-01",
            "travelEnd": "2026-08-31",
            "applicationFormUrl": None,  # its button only survives inside an HTML comment
            "documentFormUrl": "https://forms.gle/adnDYssMNVjtA2Cx7",  # movePage(): "1차 프로모션 신청한 분들에 한해서만 서류 제출"
        },
        {
            "key": "2",
            "applyStart": None,  # the page states only the deadline
            "applyUntil": "2026-09-21T18:00",
            "travelStart": "2026-10-01",
            "travelEnd": "2026-11-04",
            "applicationFormUrl": "https://forms.gle/HWrxX3iwEUrciZey6",  # live button "2차 섬 여행비 지원 혜택 신청하기"
            "documentFormUrl": None,  # not opened yet
        },
    ]


def test_real_page_procedure_rules_documents_exclusions_and_contacts() -> None:
    procedure = _fixture_record().raw_payload["procedure"]
    assert procedure["documentDeadlineDaysAfterTrip"] == 14
    assert procedure["minNights"] == 1
    assert procedure["minPaymentKrw"] == 100_000
    assert procedure["requiredDocuments"] == [
        "신분증",
        "통장사본",
        "왕복 배편 승선권 혹은 영수증",
        "실 결제 영수증 (카드, 현금 영수증 또는 송금 계좌 이체 내역 등)",
        "OTA 이용 시, 예약 및 결제 내역",
    ]
    assert procedure["photoRequirement"] == "이름, 주민등록번호, 날짜, 금액이 명확히 나온 사진만 인정됩니다."
    assert procedure["exclusions"] == [
        "중복 신청 [팀(가족, 친구, 모임)별 대표자 1인 신청 가능]",
        "중복 영수증",
        "허위 증빙",
        "간이영수증, 계좌이체 내역만 제출",
        "타 숙박 할인사업 및 지원 사업과 중복 지원",
        "육지와 연결된 섬을 여행한 경우",
        "왕복 배편 승선권, 영수증 미증빙",
        "비인가 업소 영수증",
        "법인 카드 사용 불가",
    ]
    assert procedure["contacts"] == {"email": "info@visitisland.kr", "phones": ["070-4337-5058", "070-4814-4922"]}


def test_procedure_without_document_deadline_is_parser_changed() -> None:
    from app.services.island_visit_parser import IslandVisitParserChangedError, parse_island_visit_support

    html = FIXTURE.read_text(encoding="utf-8").replace("2주 이내", "기간 내")
    with pytest.raises(IslandVisitParserChangedError):
        parse_island_visit_support(html, fetched_at=datetime(2026, 9, 14, tzinfo=UTC), today=date(2026, 9, 14))


@pytest.mark.parametrize(
    ("round_key", "today", "expected"),
    [
        ("1", date(2026, 9, 14), "current"),  # travel ended 8/31, documents still due until 9/14
        ("1", date(2026, 9, 15), "past"),
        ("2", date(2026, 9, 14), "current"),
        ("2", date(2026, 11, 18), "current"),  # 11/4 + 14 days
        ("2", date(2026, 11, 19), "past"),
    ],
)
def test_round_status_is_computed_from_dates(round_key: str, today: date, expected: str) -> None:
    from app.services.island_visit_parser import round_status

    procedure = _fixture_record().raw_payload["procedure"]
    round_ = next(item for item in procedure["rounds"] if item["key"] == round_key)
    assert round_status(round_, today=today, document_deadline_days=procedure["documentDeadlineDaysAfterTrip"]) == expected


def test_round_status_upcoming_before_apply_start() -> None:
    from app.services.island_visit_parser import round_status

    future = {"key": "3", "applyStart": "2027-03-02T10:00", "applyUntil": "2027-03-20T18:00", "travelStart": "2027-04-01", "travelEnd": "2027-05-31"}
    assert round_status(future, today=date(2027, 3, 1), document_deadline_days=14) == "upcoming"
    assert round_status(future, today=date(2027, 3, 2), document_deadline_days=14) == "current"
