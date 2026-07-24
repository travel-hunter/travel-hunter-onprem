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
    assert _descriptions(result, "applicationTarget") == [expected]


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
