from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from app.models import ExternalSourceRecord
from app.services.policy_periods import (
    budget_caveat_notices,
    evidence_from_payload,
    structured_period_items,
)
from app.services.local_half_trip_corrections import correction_for_record


StructuredDetail = dict[str, list[dict[str, object]]]


@dataclass(frozen=True)
class ExternalSourceSemanticMapping:
    target_condition: str | None
    structured_detail: StructuredDetail
    mapper_status: str
    policy_status: str | None = None
    verification_status: str | None = None


def empty_structured_detail() -> StructuredDetail:
    return {
        "supportContent": [],
        "periods": [],
        "applicationTarget": [],
        "requiredDocuments": [],
        "notes": [],
    }


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _append(items: list[dict[str, object]], *, title: str, description: str, **extra: object) -> None:
    description = _text(description)
    if not description or any(item.get("description") == description for item in items):
        return
    items.append({"title": title, "description": description, **extra})


_TIER_PATTERN = re.compile(
    r"^(?P<threshold>7만원|14만원)\s*(?P<comparison>미만|이상)\**\s*"
    r"국내\s*숙박상품\s*예약\s*시\s*(?P<discount>[2357]만원)\s*할인"
    r"\s*\((?P<stay>1박\s*이상|연박\s*이상)\)?$"
)

_EXPECTED_STAY_TIERS = [
    ("7만원", "미만", "2만원", "1박 이상"),
    ("7만원", "이상", "3만원", "1박 이상"),
    ("14만원", "미만", "5만원", "연박 이상"),
    ("14만원", "이상", "7만원", "연박 이상"),
]

_NEGATED_STAY_USAGE_PATTERN = re.compile(
    r"불가|불가능|할\s*수\s*없|하지\s*않|안\s*(?:됩|됨)|없이|제한"
)
_POSITIVE_STAY_USAGE_PATTERN = re.compile(
    r"참여\s*온라인\s*여행사.*?할인권.*?발급\s*(?:후|및|하여|하고|과)\s*사용"
)


def _stay_discount(record: ExternalSourceRecord) -> ExternalSourceSemanticMapping:
    payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    tiers = payload.get("discountTiers")
    raw_usage_method = payload.get("usageMethod")
    if not isinstance(raw_usage_method, str):
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "invalid")
    required_text = {
        key: _text(payload.get(key))
        for key in ("issuePeriod", "stayPeriod", "usageArea", "usagePlace")
    }
    required_text["usageMethod"] = _text(raw_usage_method)
    if (
        not isinstance(tiers, list)
        or len(tiers) != len(_EXPECTED_STAY_TIERS)
        or any(not value for value in required_text.values())
    ):
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "invalid")

    parsed_tiers: list[re.Match[str]] = []
    for raw_tier in tiers:
        match = _TIER_PATTERN.match(_text(raw_tier))
        if match is None:
            return ExternalSourceSemanticMapping(None, empty_structured_detail(), "invalid")
        parsed_tiers.append(match)
    parsed_values = [
        (
            match.group("threshold"),
            match.group("comparison"),
            match.group("discount"),
            _text(match.group("stay")),
        )
        for match in parsed_tiers
    ]
    if parsed_values != _EXPECTED_STAY_TIERS:
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "invalid")

    usage_method = required_text["usageMethod"]
    if (
        _NEGATED_STAY_USAGE_PATTERN.search(usage_method) is not None
        or _POSITIVE_STAY_USAGE_PATTERN.search(usage_method) is None
    ):
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "invalid")

    default_year = record.last_fetched_at.year if record.last_fetched_at is not None else 2026
    evidence = evidence_from_payload(
        {
            "issuePeriod": required_text["issuePeriod"],
            "stayPeriod": required_text["stayPeriod"],
        },
        default_year=default_year,
        source=record.source_category,
    )
    period_items = [
        {**item, "type": "application" if item.get("type") == "issue" else item.get("type")}
        for item in structured_period_items(evidence)
    ]
    if (
        len(evidence) != 2
        or len(period_items) != 2
        or [item.get("type") for item in period_items] != ["application", "usage"]
        or any(item.start_date is None or item.end_date is None for item in evidence)
    ):
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "invalid")

    detail = empty_structured_detail()
    for match in parsed_tiers:
        groups = match.groupdict()
        _append(
            detail["supportContent"],
            title="할인 혜택",
            description=(
                f"{groups['threshold']} {groups['comparison']} 국내 숙박상품 예약 시 "
                f"{groups['discount']} 할인"
            ),
        )

    _append(detail["applicationTarget"], title="신청대상", description="숙박세일페스타 대상 지역 숙박 이용자")
    _append(
        detail["applicationTarget"],
        title="신청대상",
        description="참여 온라인 여행사를 통해 국내 숙박상품을 예약하는 사용자",
    )
    _append(
        detail["applicationTarget"],
        title="신청대상",
        description="할인권 발급 후 지정 기간 내 입실 가능한 사용자",
    )

    detail["periods"] = period_items

    _append(
        detail["requiredDocuments"],
        title="필요서류",
        description="별도 제출 서류 없음 · 온라인 할인권 발급 및 예약 기준으로 적용",
    )

    issue_period = _text(payload.get("issuePeriod"))
    if "선착순" in issue_period or "선착순" in usage_method:
        _append(detail["notes"], title="비고", description="할인권은 선착순으로 발급됩니다.")
    if payload.get("earlyCloseWarning") is True or "소진" in issue_period:
        _append(detail["notes"], title="비고", description="예산 소진 시 조기 종료될 수 있습니다.")
    _append(detail["notes"], title="비고", description="세부 기준은 공식 안내에서 최종 확인하세요.")

    return ExternalSourceSemanticMapping(None, detail, "mapped")


def _local_half_trip(record: ExternalSourceRecord) -> ExternalSourceSemanticMapping:
    correction = correction_for_record(record)
    if correction is not None:
        return ExternalSourceSemanticMapping(
            correction.target_condition,
            correction.structured_detail,
            "mapped",
            correction.status,
            correction.verification_status,
        )

    payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    field_values = payload.get("field_values") if isinstance(payload.get("field_values"), dict) else {}
    raw_detail = _text(record.raw_detail_text)

    def labeled_value(label: str) -> str:
        labels = "문의전화|문의|전화|연락처|특이사항|지역화폐|신청조건|사용조건|이용조건"
        match = re.search(
            rf"(?:^|\s){re.escape(label)}\s*[:：-]\s*(.*?)(?=\s*(?:{labels})\s*[:：-]|$)",
            raw_detail,
        )
        return _text(match.group(1)) if match else ""

    currency_values = [
        _text(candidate)
        for candidate in [payload.get("localCurrency"), field_values.get("지역화폐"), labeled_value("지역화폐")]
        if _text(candidate)
    ]
    candidates = [
        payload.get("notes"),
        *(field_values.get(key) for key in ("특이사항", "신청조건", "사용조건", "이용조건")),
        *(labeled_value(key) for key in ("특이사항", "신청조건", "사용조건", "이용조건")),
        *(f"{value} 사용" for value in currency_values),
    ]
    if raw_detail and not re.search(r"문의|전화|(?:\+?\d[\d\s().-]{5,}\d)", raw_detail):
        candidates.append(raw_detail)
    target_condition = None
    for candidate in candidates:
        value = _text(candidate)
        if value and re.search(r"조건|인증|방문|결제|가맹점|지역화폐|상품|예약|쿠폰|할인|환급|지원|사용|이용|대상|숙박|식사|체험", value):
            target_condition = value
            break

    detail = empty_structured_detail()
    benefit = _text(record.benefit_value_text or record.benefit_text)
    if benefit:
        item: dict[str, object] = {"title": "혜택", "description": benefit}
        if record.benefit_value_text:
            item["amount"] = _text(record.benefit_value_text)
        detail["supportContent"].append(item)

    semantic_texts: list[str] = []
    for candidate in [payload.get("notes"), field_values.get("특이사항"), labeled_value("특이사항"), target_condition]:
        for part in re.split(r"\s*(?:,|\*|ㆍ|·|\n|/)\s*", _text(candidate)):
            part = _text(part)
            if part and part not in semantic_texts:
                semantic_texts.append(part)
    for part in semantic_texts:
        payment_document = re.match(r"(.+?결제)한?\s+(.+)$", part)
        if payment_document and re.search(r"영수증|거래내역|결제내역|인증사진|캡처|캡쳐|증빙|서류", payment_document.group(2)):
            _append(detail["applicationTarget"], title="혜택 적용 조건", description=payment_document.group(1))
            _append(detail["requiredDocuments"], title="필요 서류", description=payment_document.group(2))
        elif re.search(r"공지|고시공고|필독|문의|유의|주의|확인", part):
            _append(detail["notes"], title="비고", description=part)
        elif re.search(r"영수증|거래내역|결제내역|인증사진|캡처|캡쳐|증빙|서류", part) and not re.search(r"방문|결제|이용|사용|가맹점", part):
            _append(detail["requiredDocuments"], title="필요 서류", description=part)
        else:
            _append(detail["applicationTarget"], title="혜택 적용 조건", description=part)

    for value in currency_values:
        _append(detail["applicationTarget"], title="혜택 적용 조건", description=f"{value} 사용")

    default_year = record.last_fetched_at.year if record.last_fetched_at is not None else 2026
    evidence = evidence_from_payload(payload, default_year=default_year, source=record.source_category)
    for item in structured_period_items(evidence):
        item = dict(item)
        title = _text(item.get("title"))
        description = _text(item.get("description"))
        if title == "신청 기간" and description and not description.startswith("신청 기간:"):
            item["description"] = f"신청 기간: {description}"
        elif title in {"사용 기간", "여행 기간"} and description and not description.startswith("여행 기간:"):
            item["description"] = f"여행 기간: {description}"
        detail["periods"].append(item)
    detail["notes"].extend(
        item for item in budget_caveat_notices(evidence) if item not in detail["notes"]
    )

    return ExternalSourceSemanticMapping(target_condition, detail, "mapped")


_MAPPERS: dict[str, Callable[[ExternalSourceRecord], ExternalSourceSemanticMapping]] = {
    "local_half_trip": _local_half_trip,
    "stay_discount": _stay_discount,
}


def map_external_source_semantics(record: ExternalSourceRecord) -> ExternalSourceSemanticMapping:
    mapper = _MAPPERS.get(record.source_category or "")
    if mapper is None:
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "missing")
    return mapper(record)
