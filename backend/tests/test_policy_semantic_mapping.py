from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

import pytest

from app.models import ExternalSourceRecord


STAY_PAYLOAD = {
    "issuePeriod": "2026.6.11(목)~8.17(월) 매일 오전 10시부터 선착순 발급 (단, 기한 내 소진 시 발급 불가)",
    "stayPeriod": "2026. 6.11(목)~8.17(월)",
    "usageArea": "비수도권 인구감소지역(85개 지자체)",
    "usagePlace": "국내숙박 업소 / 대실 사용 불가",
    "usageMethod": "참여 온라인 여행사를 통한 숙박 할인권 발급 후 사용 / 1인 1매 사용(선착순)",
    "discountTiers": [
        "7만원 미만* 국내 숙박상품 예약 시 2만원 할인(1박 이상)",
        "7만원 이상* 국내 숙박상품 예약 시 3만원 할인(1박 이상)",
        "14만원 미만** 국내 숙박상품 예약 시 5만원 할인(연박 이상)",
        "14만원 이상** 국내 숙박상품 예약 시 7만원 할인(연박 이상)",
    ],
    "eligibleAreas": [{"sido": "강원", "cities": ["고성군"]}],
    "eligibleAreaCount": 1,
    "earlyCloseWarning": True,
}


def _record(*, source_category: str = "stay_discount", raw_payload: object = STAY_PAYLOAD) -> ExternalSourceRecord:
    return ExternalSourceRecord(
        id=33,
        source_name="대한민국 숙박세일 페스타",
        source_type="official_campaign",
        source_category=source_category,
        external_id="stay-discount",
        canonical_key="stay-discount-snapshot",
        logical_key="stay-discount:2026-summer",
        detail_url="https://ktostay.visitkorea.or.kr/",
        collected_page_url="https://ktostay.visitkorea.or.kr/",
        title="2026 대한민국 숙박세일 페스타",
        status="active",
        benefit_text="숙박 할인권",
        benefit_value_text="2/3/5/7만원 할인권",
        extracted_amount_krw=70_000,
        contact_text="할인혜택과 발급기간을 합친 과거 composite",
        raw_list_text="원문 목록",
        raw_detail_text="원문 상세",
        raw_payload=raw_payload,
        last_fetched_at=datetime(2026, 6, 16, tzinfo=UTC),
        freshness_status="fresh",
    )


def _map(record: ExternalSourceRecord):
    from app.services.policy_semantic_mapping import map_external_source_semantics

    return map_external_source_semantics(record)


def _descriptions(result, section: str) -> list[str]:
    return [str(item["description"]) for item in result.structured_detail[section]]


def _local_half_trip_record(source_id: int) -> ExternalSourceRecord:
    return ExternalSourceRecord(
        id=source_id,
        source_name="여행가는 달",
        source_type="official_campaign",
        source_category="local_half_trip",
        external_id=f"tour50-{source_id}",
        canonical_key=f"tour50-{source_id}",
        detail_url="https://example.com/detail",
        collected_page_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
        title=f"대한민국 구석구석 반값여행 {source_id}",
        status="active",
        benefit_text="대한민국 구석구석 반값여행",
        benefit_value_text="여행비 50% 환급",
        raw_detail_text="legacy polluted detail",
        raw_payload={"notes": "영수증과 인증사진이 섞인 legacy 원문"},
        last_fetched_at=datetime(2026, 7, 16, tzinfo=UTC),
        freshness_status="fresh",
    )


def test_local_half_trip_five_manifest_overrides_split_target_documents_periods() -> None:
    from app.services.local_half_trip_corrections import local_half_trip_five_corrections

    corrections = local_half_trip_five_corrections()
    forbidden_target_terms = ("영수증", "결제내역", "인증사진", "인증 사진", "캡처", "캡쳐", "이용 확인서")

    for source_id in (20, 24, 32, 21, 27):
        result = _map(_local_half_trip_record(source_id))
        correction = corrections[source_id]

        assert result.mapper_status == "mapped"
        assert result.policy_status == correction.status
        assert result.verification_status == correction.verification_status
        assert result.target_condition == correction.target_condition
        assert result.structured_detail == correction.structured_detail
        assert set(result.structured_detail) == {
            "supportContent",
            "periods",
            "applicationTarget",
            "requiredDocuments",
            "notes",
        }
        target_text = " ".join(_descriptions(result, "applicationTarget"))
        document_text = " ".join(_descriptions(result, "requiredDocuments"))
        assert not any(term in target_text for term in forbidden_target_terms)
        assert any(term in document_text for term in forbidden_target_terms)
        assert result.structured_detail["supportContent"]
        assert result.structured_detail["periods"]


def test_local_half_trip_five_gocheang_fails_closed_from_manifest() -> None:
    result = _map(_local_half_trip_record(32))

    assert result.policy_status == "hidden"
    assert result.verification_status == "needs_review"
    assert any(
        "재확인" in item["description"] or "마감" in item["description"]
        for item in result.structured_detail["notes"]
    )


def test_stay_mapper_strictly_splits_support_periods_target_documents_notes() -> None:
    result = _map(_record())

    assert result.mapper_status == "mapped"
    assert result.target_condition is None
    assert len(result.structured_detail) == 5
    assert len(result.structured_detail["supportContent"]) == 4
    benefits = _descriptions(result, "supportContent")
    conditions = _descriptions(result, "applicationTarget")
    periods = _descriptions(result, "periods")
    notices = _descriptions(result, "notes")

    assert benefits == [
        "7만원 미만 국내 숙박상품 예약 시 2만원 할인",
        "7만원 이상 국내 숙박상품 예약 시 3만원 할인",
        "14만원 미만 국내 숙박상품 예약 시 5만원 할인",
        "14만원 이상 국내 숙박상품 예약 시 7만원 할인",
    ]
    assert conditions == [
        "숙박세일페스타 대상 지역 숙박 이용자",
        "참여 온라인 여행사를 통해 국내 숙박상품을 예약하는 사용자",
        "할인권 발급 후 지정 기간 내 입실 가능한 사용자",
    ]
    assert len(periods) == 2
    assert {item["type"] for item in result.structured_detail["periods"]} == {"application", "usage"}
    assert any("선착순" in item for item in notices)
    assert any("소진" in item or "조기 종료" in item for item in notices)
    assert result.structured_detail["requiredDocuments"] == [
        {
            "title": "필요서류",
            "description": "별도 제출 서류 없음 · 온라인 할인권 발급 및 예약 기준으로 적용",
        }
    ]
    assert any("공식 안내" in item for item in notices)

    forbidden_target_or_notice = " ".join([result.target_condition or "", *notices])
    assert "7만원 미만" not in forbidden_target_or_notice
    assert "발급기간" not in forbidden_target_or_notice
    assert "입실기간" not in forbidden_target_or_notice
    assert not set(benefits) & set(conditions + periods + notices)
    assert not set(periods) & set(conditions + notices)


def test_stay_mapper_rejects_malformed_tiers_without_reclassifying_raw_blob() -> None:
    payload = dict(STAY_PAYLOAD)
    payload["discountTiers"] = ["VIP 고객에게 상황에 따라 큰 혜택 제공"]

    result = _map(_record(raw_payload=payload))

    assert result.mapper_status == "invalid"
    assert result.target_condition is None
    assert result.structured_detail["supportContent"] == []
    assert result.structured_detail["applicationTarget"] == []
    assert result.structured_detail["notes"] == []
    assert "VIP 고객" not in str(result.structured_detail)


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("issuePeriod", ""),
        ("stayPeriod", None),
        ("usageArea", ""),
        ("usagePlace", None),
        ("usageMethod", ""),
        ("issuePeriod", "날짜 미정"),
        ("stayPeriod", "추후 공지"),
        ("issuePeriod", "2026.6.11부터 선착순 발급"),
        ("stayPeriod", "2026.8.17까지 입실"),
        ("discountTiers", STAY_PAYLOAD["discountTiers"][:3]),
        ("discountTiers", [*STAY_PAYLOAD["discountTiers"], STAY_PAYLOAD["discountTiers"][0]]),
        (
            "discountTiers",
            [
                STAY_PAYLOAD["discountTiers"][1],
                STAY_PAYLOAD["discountTiers"][0],
                *STAY_PAYLOAD["discountTiers"][2:],
            ],
        ),
        (
            "discountTiers",
            [
                STAY_PAYLOAD["discountTiers"][0].replace("2만원 할인", "3만원 할인"),
                *STAY_PAYLOAD["discountTiers"][1:],
            ],
        ),
        ("usageMethod", "할인권 발급 후 사용"),
    ],
    ids=[
        "missing-issue-period",
        "missing-stay-period",
        "missing-usage-area",
        "missing-usage-place",
        "missing-usage-method",
        "malformed-issue-period",
        "malformed-stay-period",
        "issue-period-missing-end",
        "stay-period-missing-start",
        "three-tiers",
        "five-tiers",
        "wrong-tier-order",
        "wrong-tier-discount",
        "incompatible-usage-method",
    ],
)
def test_stay_mapper_requires_complete_exact_compatible_evidence(
    mutation: str,
    value: object,
) -> None:
    payload = deepcopy(STAY_PAYLOAD)
    payload[mutation] = value

    result = _map(_record(raw_payload=payload))

    assert result.mapper_status == "invalid"
    assert result.target_condition is None
    assert result.structured_detail == {
        "supportContent": [],
        "applicationTarget": [],
        "periods": [],
        "requiredDocuments": [],
        "notes": [],
    }


@pytest.mark.parametrize(
    "usage_method",
    [
        {"method": STAY_PAYLOAD["usageMethod"]},
        [STAY_PAYLOAD["usageMethod"]],
        1,
        True,
    ],
    ids=["dict", "list", "integer", "boolean"],
)
def test_stay_mapper_rejects_non_string_usage_method(usage_method: object) -> None:
    payload = deepcopy(STAY_PAYLOAD)
    payload["usageMethod"] = usage_method

    result = _map(_record(raw_payload=payload))

    assert result.mapper_status == "invalid"
    assert result.structured_detail == {
        "supportContent": [],
        "applicationTarget": [],
        "periods": [],
        "requiredDocuments": [],
        "notes": [],
    }


@pytest.mark.parametrize(
    ("usage_method", "expected_status"),
    [
        ("참여 온라인 여행사에서는 할인권 발급 및 사용이 불가합니다", "invalid"),
        ("참여 온라인 여행사를 통한 숙박 할인권 발급 불가", "invalid"),
        ("참여 온라인 여행사를 통한 숙박 할인권 사용 불가", "invalid"),
        ("참여 온라인 여행사를 통한 숙박 할인권 이용 불가", "invalid"),
        ("참여 온라인 여행사를 통한 숙박 할인권 사용", "invalid"),
        ("참여 온라인 여행사를 통한 숙박 할인권 발급", "invalid"),
        ("참여 온라인 여행사를 통한 숙박 할인권 발급 후 사용", "mapped"),
    ],
    ids=[
        "negated-issuance-and-use",
        "issuance-unavailable",
        "use-unavailable",
        "usage-unavailable",
        "missing-issuance",
        "missing-use",
        "positive-issuance-and-use",
    ],
)
def test_stay_mapper_requires_positive_compatible_usage_method_evidence(
    usage_method: str,
    expected_status: str,
) -> None:
    payload = deepcopy(STAY_PAYLOAD)
    payload["usageMethod"] = usage_method

    result = _map(_record(raw_payload=payload))

    assert result.mapper_status == expected_status
    if expected_status == "mapped":
        assert _descriptions(result, "applicationTarget")[1] == "참여 온라인 여행사를 통해 국내 숙박상품을 예약하는 사용자"
    else:
        assert all(not items for items in result.structured_detail.values())


@pytest.mark.parametrize(
    ("raw_payload", "raw_detail_text"),
    [
        ({"field_values": {"지역화폐": "chak 앱(모바일 강진사랑상품권)"}}, None),
        ({}, "지역화폐 : chak 앱(모바일 강진사랑상품권)"),
    ],
    ids=["structured-field", "labeled-detail"],
)
def test_local_half_trip_currency_evidence_is_an_explicit_stable_target_condition(
    raw_payload: dict[str, object],
    raw_detail_text: str | None,
) -> None:
    record = _record(source_category="local_half_trip", raw_payload=raw_payload)
    record.raw_detail_text = raw_detail_text

    result = _map(record)

    expected = "chak 앱(모바일 강진사랑상품권) 사용"
    assert result.mapper_status == "mapped"
    assert result.target_condition == expected
    targets = _descriptions(result, "applicationTarget")
    benefits = _descriptions(result, "supportContent")
    assert expected not in targets
    assert any("반값여행 참여 혜택" in item for item in targets)
    assert expected in benefits
    assert any("영수증" in item for item in _descriptions(result, "requiredDocuments"))
    assert any("공식 혜택 안내" in item for item in _descriptions(result, "notes"))


def test_local_half_trip_uses_detail_participant_target_as_application_target() -> None:
    record = _record(
        source_category="local_half_trip",
        raw_payload={
            "participantTarget": (
                "강진군 외 지역에 거주하는 사전신청 관광객 누구나\n"
                "※ 단, 완도군, 해남군, 영암군, 장흥군 거주자는 지원 대상 제외"
            ),
            "field_values": {
                "지역화폐": "chak 앱(모바일 강진사랑상품권)",
                "특이사항": "강진군 관광지 2개소 이상 방문",
            },
        },
    )
    record.city = "강진"

    result = _map(record)

    assert _descriptions(result, "applicationTarget") == [
        "강진군 외 지역에 거주하는 사전신청 관광객 누구나",
        "※ 단, 완도군, 해남군, 영암군, 장흥군 거주자는 지원 대상 제외",
    ]
    assert "강진군 관광지 2개소 이상 방문" in _descriptions(result, "supportContent")
    assert "chak 앱(모바일 강진사랑상품권) 사용" in _descriptions(result, "supportContent")
    assert all("Chak" not in item for item in _descriptions(result, "applicationTarget"))


def test_local_half_trip_uses_detail_support_documents_and_notes() -> None:
    record = _record(
        source_category="local_half_trip",
        raw_payload={
            "participantTarget": "강진군 외 지역에 거주하는 사전신청 관광객 누구나",
            "supportDetail": "강진 여행 비용의 50% 환급\n모바일 강진사랑상품권으로 지급",
            "requiredDocumentsDetail": "거래내역 영수증\n관광지 방문 인증사진",
            "detailNotes": "예산 소진 시 조기 마감",
        },
    )
    record.city = "강진"

    result = _map(record)

    assert "강진 여행 비용의 50% 환급" in _descriptions(result, "supportContent")
    assert "모바일 강진사랑상품권으로 지급" in _descriptions(result, "supportContent")
    assert "거래내역 영수증" in _descriptions(result, "requiredDocuments")
    assert "관광지 방문 인증사진" in _descriptions(result, "requiredDocuments")
    assert "예산 소진 시 조기 마감" in _descriptions(result, "notes")
    assert _descriptions(result, "applicationTarget") == [
        "강진군 외 지역에 거주하는 사전신청 관광객 누구나"
    ]


def test_local_half_trip_strips_raw_bullet_prefixes_from_support_content() -> None:
    record = _record(
        source_category="local_half_trip",
        raw_payload={
            "participantTarget": "강진군 외 지역에 거주하는 사전신청 관광객 누구나",
            "supportDetail": (
                ": 총 3만 원 이상 소비 시, 사용금액의 50% 최대 10만 원까지 지원\n"
                ": 총 5만 원 이상 소비 시, 사용금액의 50% 최대 20만 원까지 지원\n"
                "ㆍ18만 원 소비 시 12만 5천 원 지원\n"
                "ㆍ20만 원 소비 시 14만 원 지원"
            ),
        },
    )
    record.city = "강진"

    result = _map(record)

    support_descriptions = _descriptions(result, "supportContent")
    assert "총 3만 원 이상 소비 시, 사용금액의 50% 최대 10만 원까지 지원" in support_descriptions
    assert "총 5만 원 이상 소비 시, 사용금액의 50% 최대 20만 원까지 지원" in support_descriptions
    assert "18만 원 소비 시 12만 5천 원 지원" in support_descriptions
    assert "20만 원 소비 시 14만 원 지원" in support_descriptions
    assert not any(description.startswith((":", "ㆍ", "·")) for description in support_descriptions)


def test_local_half_trip_public_manual_correction_enriches_hapcheon_and_wando() -> None:
    hapcheon = _record(source_category="local_half_trip", raw_payload={})
    hapcheon.id = 25
    hapcheon.city = "합천"
    hapcheon.status = "scheduled"
    hapcheon.detail_url = "https://www.hctour.kr/"
    wando = _record(source_category="local_half_trip", raw_payload={})
    wando.id = 31
    wando.city = "완도"
    wando.status = "scheduled"
    wando.detail_url = "https://www.wandotrip.kr/index.php"

    hapcheon_result = _map(hapcheon)
    wando_result = _map(wando)

    assert hapcheon_result.policy_status == "active"
    assert hapcheon_result.verification_status == "fresh"
    assert any("최대 50만원" in item for item in _descriptions(hapcheon_result, "supportContent"))
    assert any("합천군 외 지역" in item for item in _descriptions(hapcheon_result, "applicationTarget"))
    assert any("숙박이용확인서" in item for item in _descriptions(hapcheon_result, "requiredDocuments"))
    assert wando_result.policy_status == "active"
    assert any("모바일 완도사랑상품권" in item for item in _descriptions(wando_result, "supportContent"))
    assert any("2026-07-10" in item["description"] for item in wando_result.structured_detail["periods"])
    assert any("Chak 앱" in item for item in _descriptions(wando_result, "requiredDocuments"))


def test_digital_tourism_mapper_outputs_digital_only_sections() -> None:
    record = _record(
        source_category="digital_tourism_resident_card",
        raw_payload={"notes": "대한민국 반값여행 최대 20만원 50% 환급"},
    )
    record.title = "[하동] 디지털관광주민증 혜택"
    record.city = "하동"
    record.benefit_text = "대한민국 반값여행 최대 20만원 50% 환급"
    record.benefit_value_text = "50% 환급"

    result = _map(record)
    serialized = str(result.structured_detail)

    assert result.mapper_status == "mapped"
    assert result.target_condition == "하동 디지털관광주민증을 발급한 여행자"
    assert _descriptions(result, "supportContent") == [
        "디지털관광주민증 발급 지역의 숙박, 식음, 체험, 관광지 제휴 혜택"
    ]
    assert _descriptions(result, "applicationTarget") == [
        "하동 디지털관광주민증을 발급한 여행자",
        "VisitKorea/대한민국 구석구석에서 디지털관광주민증을 발급하고 제휴처에서 제시해야 합니다.",
    ]
    assert _descriptions(result, "requiredDocuments") == [
        "별도 제출 서류 없음, 디지털관광주민증 발급 및 제시 기준으로 적용"
    ]
    assert _descriptions(result, "notes") == [
        "제휴처별 할인율, 운영 기간, 이용 조건은 VisitKorea 공식 안내에서 최종 확인하세요.",
        "지역별 제휴처와 혜택은 변동될 수 있습니다.",
    ]
    assert "반값여행" not in serialized
    assert "50% 환급" not in serialized
    assert "최대 20만원" not in serialized



def test_digital_tourism_mapper_splits_summary_and_clickable_category_highlights() -> None:
    record = _record(
        source_category="digital_tourism_resident_card",
        raw_payload={
            "partnerBenefits": [
                {
                    "memberId": "cdb03f3e-180d-11ef-b16c-0242ac130002",
                    "categoryCode": "FDRK",
                    "categoryName": "식음료",
                    "name": "로우풀",
                    "intro": "호수뷰와 마운틴뷰가 조화로운 대형카페",
                    "summary": "음료 구매시 아메리카노 리필 1회",
                    "usageCount": 200,
                }
            ],
            "partnerBenefitSummary": {
                "totalCount": 1,
                "categoryCounts": {"식음료": 1},
                "displayLimit": 8,
            },
            "partnerBenefitCategoryHighlights": [
                {
                    "categoryCode": "FDRK",
                    "categoryName": "식음료",
                    "totalCount": 1,
                    "remainingCount": 0,
                    "representative": {
                        "memberId": "cdb03f3e-180d-11ef-b16c-0242ac130002",
                        "categoryCode": "FDRK",
                        "categoryName": "식음료",
                        "name": "로우풀",
                        "intro": "호수뷰와 마운틴뷰가 조화로운 대형카페",
                        "summary": "음료 구매시 아메리카노 리필 1회",
                        "usageCount": 200,
                    },
                }
            ],
        },
    )
    record.title = "[합천] 디지털관광주민증 혜택"
    record.city = "합천"

    result = _map(record)
    support = result.structured_detail["supportContent"]

    assert support[0]["title"] == "핵심 혜택"
    assert support[1]["title"] == "카테고리별 인기 혜택"
    assert support[2]["description"] == "🍽️ 로우풀: 음료 구매시 아메리카노 리필 1회\n호수뷰와 마운틴뷰가 조화로운 대형카페"
    assert support[2]["url"] == (
        "https://korean.visitkorea.or.kr/dgtourcard/biz/mbrb/mbrbPtcl.do?"
        "mbrbId=cdb03f3e-180d-11ef-b16c-0242ac130002"
    )
    assert "·" not in str(support)
    assert "외 1개 혜택" not in str(support)


def test_digital_tourism_mapper_uses_partner_benefits_for_rich_support_content() -> None:
    record = _record(
        source_category="digital_tourism_resident_card",
        raw_payload={
            "partnerBenefits": [
                {
                    "memberId": "pc-1",
                    "categoryCode": "VWNG",
                    "categoryName": "관람",
                    "name": "평창올림픽플라자",
                    "intro": "올림픽 레거시 전시장",
                    "summary": "관람료 할인",
                    "detail": "대인 15,000원 > 8,000원",
                    "usageCount": 466,
                    "totalCount": 1,
                },
                {
                    "memberId": "pc-2",
                    "categoryCode": "EXPRN",
                    "categoryName": "체험",
                    "name": "대관령코스터",
                    "intro": "체험시설",
                    "summary": "이용권 20% 할인",
                    "detail": "이용권 20% 할인",
                    "usageCount": 20,
                    "totalCount": 3,
                },
                {
                    "memberId": "pc-3",
                    "categoryCode": "EXPRN",
                    "categoryName": "체험",
                    "name": "대관령목장",
                    "intro": "목장 체험",
                    "summary": "체험료 할인",
                    "detail": "체험료 할인",
                    "usageCount": 10,
                    "totalCount": 3,
                },
            ],
            "partnerBenefitSummary": {
                "totalCount": 4,
                "categoryCounts": {"관람": 1, "체험": 3},
                "displayLimit": 8,
            },
            "partnerBenefitCategoryHighlights": [
                {
                    "categoryCode": "VWNG",
                    "categoryName": "관람",
                    "totalCount": 1,
                    "remainingCount": 0,
                    "representative": {
                        "memberId": "pc-1",
                        "categoryCode": "VWNG",
                        "categoryName": "관람",
                        "name": "평창올림픽플라자",
                        "intro": "올림픽 레거시 전시장",
                        "summary": "관람료 할인",
                        "detail": "대인 15,000원 > 8,000원",
                        "usageCount": 466,
                        "totalCount": 1,
                    },
                },
                {
                    "categoryCode": "EXPRN",
                    "categoryName": "체험",
                    "totalCount": 3,
                    "remainingCount": 2,
                    "representative": {
                        "memberId": "pc-2",
                        "categoryCode": "EXPRN",
                        "categoryName": "체험",
                        "name": "대관령코스터",
                        "intro": "체험시설",
                        "summary": "이용권 20% 할인",
                        "detail": "이용권 20% 할인",
                        "usageCount": 20,
                        "totalCount": 3,
                    },
                },
            ],
        },
    )
    record.title = "[평창] 디지털관광주민증 혜택"
    record.city = "평창"

    result = _map(record)
    descriptions = _descriptions(result, "supportContent")

    assert descriptions[0] == "평창 제휴처 4곳의 숙박, 식음, 체험, 관광지 혜택을 제공합니다. 주요 분야: 관람 1곳, 체험 3곳."
    assert descriptions[1] == "인기순 대표 제휴처와 주요 혜택을 카테고리별로 정리했습니다."
    assert descriptions[2] == "🎟️ 평창올림픽플라자: 관람료 할인\n올림픽 레거시 전시장"
    assert descriptions[3] == "🎡 대관령코스터: 이용권 20% 할인\n체험시설"
    assert len(descriptions) == 4
    assert "·" not in str(descriptions)
    assert "외 2개 혜택" not in str(descriptions)

def test_digital_tourism_mapper_does_not_stringify_payload_note_lists() -> None:
    record = _record(
        source_category="digital_tourism_resident_card",
        raw_payload={"notes": ["지역별 제휴처와 혜택은 변동될 수 있습니다."]},
    )
    record.title = "[하동] 디지털관광주민증 혜택"
    record.city = "하동"

    result = _map(record)
    notes = _descriptions(result, "notes")

    assert notes == [
        "제휴처별 할인율, 운영 기간, 이용 조건은 VisitKorea 공식 안내에서 최종 확인하세요.",
        "지역별 제휴처와 혜택은 변동될 수 있습니다.",
    ]
    assert not any(note.startswith("[") for note in notes)


def test_unknown_mapper_is_explicitly_empty_and_fail_closed() -> None:
    result = _map(_record(source_category="future_unknown_campaign"))

    assert result.mapper_status == "missing"
    assert result.target_condition is None
    assert result.structured_detail == {
        "supportContent": [],
        "applicationTarget": [],
        "periods": [],
        "requiredDocuments": [],
        "notes": [],
    }
