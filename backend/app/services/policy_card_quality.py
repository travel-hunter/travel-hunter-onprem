from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.services.travelmonth_normalizer import normalize_text


FALLBACK_CARD_COPY = "혜택 상세 확인"
MAX_CARD_COPY_LENGTH = 40

_BENEFIT_ISSUES = {
    "benefit_missing",
    "benefit_not_summary",
    "benefit_navigation_text",
    "benefit_site_chrome",
    "benefit_unit_ambiguous",
}
_NAVIGATION_TEXT_PATTERN = re.compile(
    r"^(?:할인|혜택|신청|예약|자세히|공식\s*사이트).*(?:보러\s*가기|보기|바로\s*가기)$",
    re.IGNORECASE,
)
_SITE_CHROME_PATTERN = re.compile(
    r"copyright|all\s+rights\s+reserved|통신판매업신고|(?:^|\s)tel\s*:|"
    r"본\s*사이트의\s*일부|한국관광공사\s*:\s*\[?\d{5}",
    re.IGNORECASE,
)
_SECTION_LABELS = {
    "지원내용",
    "지원 내용",
    "지원내용 및 금액",
    "지원 내용 및 금액",
    "할인혜택",
    "할인 혜택",
    "혜택내용",
    "혜택 내용",
    "신청방법",
    "신청 방법",
}


@dataclass(frozen=True)
class CardCopyResult:
    summary: str | None
    evidence: str
    issues: tuple[str, ...]

    @property
    def display_text(self) -> str:
        return self.summary or FALLBACK_CARD_COPY

    def to_payload(self) -> dict[str, object]:
        return {
            "version": 1,
            "summary": self.summary,
            "evidence": self.evidence,
            "issues": list(self.issues),
        }


def evaluate_card_copy(
    *,
    summary: str | None,
    evidence: str,
    issues: tuple[str, ...] = (),
) -> CardCopyResult:
    normalized_summary = normalize_text(summary or "") or None
    normalized_evidence = normalize_text(evidence)
    detected = list(_unique(issues))

    if normalized_summary is None:
        if not any(issue in _BENEFIT_ISSUES for issue in detected):
            detected.append("benefit_missing")
    elif _NAVIGATION_TEXT_PATTERN.fullmatch(normalized_summary):
        detected.append("benefit_navigation_text")
    elif _SITE_CHROME_PATTERN.search(normalized_summary):
        detected.append("benefit_site_chrome")
    elif normalized_summary in _SECTION_LABELS or len(normalized_summary) > MAX_CARD_COPY_LENGTH:
        detected.append("benefit_not_summary")

    normalized_issues = _unique(detected)
    if any(issue in _BENEFIT_ISSUES for issue in normalized_issues):
        normalized_summary = None

    return CardCopyResult(
        summary=normalized_summary,
        evidence=normalized_evidence,
        issues=normalized_issues,
    )


def card_copy_for_record(record: Any) -> CardCopyResult:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    if "cardCopy" not in raw_payload:
        return evaluate_card_copy(
            summary=getattr(record, "benefit_value_text", None),
            evidence=(
                getattr(record, "raw_detail_text", None)
                or getattr(record, "benefit_text", None)
                or ""
            ),
        )

    payload = raw_payload.get("cardCopy")
    if not _valid_payload(payload):
        evidence = (
            payload.get("evidence", "")
            if isinstance(payload, dict) and isinstance(payload.get("evidence"), str)
            else getattr(record, "raw_detail_text", None)
            or getattr(record, "benefit_text", None)
            or ""
        )
        return evaluate_card_copy(
            summary=None,
            evidence=evidence,
            issues=("benefit_not_summary",),
        )

    return evaluate_card_copy(
        summary=payload["summary"],
        evidence=payload["evidence"],
        issues=tuple(payload["issues"]),
    )


def _valid_payload(payload: object) -> bool:
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return False
    if payload.get("summary") is not None and not isinstance(payload.get("summary"), str):
        return False
    if not isinstance(payload.get("evidence"), str):
        return False
    issues = payload.get("issues")
    return isinstance(issues, list) and all(isinstance(issue, str) for issue in issues)


def _unique(values: object) -> tuple[str, ...]:
    result: list[str] = []
    for value in values:
        if isinstance(value, str) and value and value not in result:
            result.append(value)
    return tuple(result)
