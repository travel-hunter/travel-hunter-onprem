from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.policy_card_quality import (
    card_copy_for_record,
    evaluate_card_copy,
    public_card_summary_for_policy,
)


@pytest.mark.parametrize(
    ("summary", "code"),
    [
        (None, "benefit_missing"),
        ("할인혜택 보러가기", "benefit_navigation_text"),
        ("Copyright 한국관광공사", "benefit_site_chrome"),
        ("지원내용 및 금액", "benefit_not_summary"),
        ("가" * 41, "benefit_not_summary"),
    ],
)
def test_unsafe_summary_is_held(summary: str | None, code: str) -> None:
    result = evaluate_card_copy(summary=summary, evidence="공식 본문")

    assert code in result.issues
    assert result.display_text == "혜택 상세 확인"


@pytest.mark.parametrize(
    ("summary", "code"),
    [
        # 2026-09-16 개발서버 조사에서 실제 카드에 들어갔던 값들 - 어느 것도 요약으로 살아남으면 안 된다
        ("할인혜택 보러가기", "benefit_navigation_text"),  # 173·175·177 링크 글자
        (
            "할인혜택 보러가기 한국관광공사 : [26464] 강원특별자치도 원주시 세계로 10 TEL : 033-738-3000 통신판매업신고",
            "benefit_site_chrome",
        ),  # 179 기관 주소·전화·신고번호
        ("연안지역 기초 지자체 상품 구매자 대상 저공해 렌터카 * 할인쿠폰 제공", "benefit_not_summary"),  # 178 문장 통째
        ("및 금액", "benefit_not_summary"),  # 202 제목 "지원 내용 및 금액" 의 뒷조각
        ("지원 내용 및 금액", "benefit_not_summary"),  # 섹션 배너
    ],
)
def test_real_world_contamination_never_becomes_card_copy(summary: str, code: str) -> None:
    result = evaluate_card_copy(summary=summary, evidence=summary)

    assert result.summary is None
    assert code in result.issues


@pytest.mark.parametrize("summary", ["최대 3만 포인트", "무료 입장", "가맹점별 할인"])
def test_non_cash_and_non_numeric_benefits_survive(summary: str) -> None:
    result = evaluate_card_copy(summary=summary, evidence=summary)

    assert result.display_text == summary
    assert not result.issues


def test_period_warning_does_not_erase_valid_benefit() -> None:
    result = evaluate_card_copy(
        summary="최대 50% 할인",
        evidence="원문",
        issues=("period_ambiguous",),
    )

    assert result.display_text == "최대 50% 할인"
    assert result.issues == ("period_ambiguous",)


def test_payload_is_revalidated_instead_of_trusted() -> None:
    record = SimpleNamespace(
        raw_payload={
            "cardCopy": {
                "version": 1,
                "summary": "할인혜택 보러가기",
                "evidence": "공식 본문",
                "issues": [],
            }
        },
        benefit_value_text="최대 3만원 할인",
        benefit_text="원문 혜택",
    )

    result = card_copy_for_record(record)

    assert result.summary is None
    assert result.display_text == "혜택 상세 확인"
    assert result.issues == ("benefit_navigation_text",)


def test_malformed_payload_is_held() -> None:
    record = SimpleNamespace(
        raw_payload={"cardCopy": {"version": 2, "summary": ["최대 3만원"]}},
        benefit_value_text="최대 3만원 할인",
        benefit_text="원문 혜택",
    )

    result = card_copy_for_record(record)

    assert result.summary is None
    assert result.issues == ("benefit_not_summary",)


def test_legacy_record_uses_only_benefit_value_text() -> None:
    record = SimpleNamespace(
        raw_payload={},
        benefit_value_text=None,
        benefit_text="원문 전체 문장은 카드 요약으로 사용하지 않는다",
    )

    result = card_copy_for_record(record)

    assert result.summary is None
    assert result.evidence == "원문 전체 문장은 카드 요약으로 사용하지 않는다"
    assert result.issues == ("benefit_missing",)


def _policy(**fields):
    base = {"card_summary": None, "benefit_detail": None, "benefit_amount": None}
    return SimpleNamespace(**{**base, **fields})


def test_public_card_summary_prefers_the_approved_value() -> None:
    policy = _policy(card_summary="최대 2만원 렌터카 할인", benefit_detail="할인혜택 보러가기")
    assert public_card_summary_for_policy(policy) == "최대 2만원 렌터카 할인"


def test_public_card_summary_keeps_a_clean_legacy_amount_when_nothing_is_stored() -> None:
    # 마이그레이션 직후 - 저장값은 없지만 기존 amount 가 깨끗하면 카드 혜택이 사라지지 않는다
    assert public_card_summary_for_policy(_policy(benefit_detail="최대 30%")) == "최대 30%"
    assert public_card_summary_for_policy(_policy(benefit_amount=50000)) == "최대 5만원"


@pytest.mark.parametrize(
    "legacy_amount",
    [
        "할인혜택 보러가기",
        "할인혜택 보러가기 한국관광공사 : [26464] 강원특별자치도 원주시 세계로 10 TEL : 033-738-3000 통신판매업신고",
        "연안지역 기초 지자체 상품 구매자 대상 저공해 렌터카 * 할인쿠폰 제공",
        "및 금액",
        "",
    ],
)
def test_public_card_summary_hides_a_polluted_legacy_amount(legacy_amount: str) -> None:
    # 오염된 amount 는 카드에서만 사라진다. amount 자체(상세·일정)는 이 함수가 건드리지 않는다.
    assert public_card_summary_for_policy(_policy(benefit_detail=legacy_amount)) is None


def test_public_card_summary_revalidates_a_stored_value_with_current_rules() -> None:
    # 예전 규칙으로 승인된 값이 지금 규칙에 걸리면 저장값을 믿지 않고 amount 로 내려간다
    policy = _policy(card_summary="및 금액", benefit_detail="최대 30%")
    assert public_card_summary_for_policy(policy) == "최대 30%"
