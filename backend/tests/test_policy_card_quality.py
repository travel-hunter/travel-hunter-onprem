from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.policy_card_quality import card_copy_for_record, evaluate_card_copy


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
