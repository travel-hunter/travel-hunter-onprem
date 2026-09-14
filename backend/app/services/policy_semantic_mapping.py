from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Callable

from app.models import ExternalSourceRecord
from app.services import digital_tourism_resident_card as dgtour_identity
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


def _display_description_text(value: object) -> str:
    text = _text(value)
    return re.sub(r"^(?:[:：ㆍ·•*\-–—]+\s*)+", "", text).strip()


def _append(items: list[dict[str, object]], *, title: str, description: str, **extra: object) -> None:
    description = _display_description_text(description)
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


def _local_half_trip_city(record: ExternalSourceRecord) -> str:
    city = _text(record.city)
    if city:
        return city
    title = _text(record.title)
    match = re.match(r"^\[([^\]]+)\]", title)
    if match:
        return _text(match.group(1))
    match = re.match(r"^(.+?)\s+대한민국\s+반값여행", title)
    return _text(match.group(1)) if match else ""


def _local_half_trip_default_target(record: ExternalSourceRecord) -> str:
    city = _local_half_trip_city(record)
    city_prefix = f"{city} 지역" if city else "해당 참여지역"
    return f"{city_prefix} 반값여행 참여 혜택을 신청하고, 공식 안내의 사전 신청·승인·이용 조건을 충족한 여행자"


def _split_detail_lines(value: object) -> list[str]:
    lines: list[str] = []
    for part in re.split(r"[ \t]*\r?\n[ \t]*", str(value or "")):
        text = _text(part)
        if text and text not in lines:
            lines.append(text)
    return lines


def _append_local_half_trip_default_sections(
    detail: StructuredDetail,
    *,
    record: ExternalSourceRecord,
) -> None:
    city = _local_half_trip_city(record)
    city_prefix = f"{city} 지역" if city else "참여지역"
    benefit = _text(record.benefit_value_text or record.benefit_text)
    has_specific_support = any(item.get("title") == "지원내용" for item in detail["supportContent"])
    if benefit and not has_specific_support:
        _append(
            detail["supportContent"],
            title="지원내용",
            description=(
                f"{city_prefix} 여행 후 공식 안내에서 정한 소비·방문 인증 기준을 충족하면 "
                f"{benefit} 혜택을 받을 수 있습니다."
            ),
        )
    if not has_specific_support:
        _append(
            detail["supportContent"],
            title="지원내용",
            description=(
                "숙박·식사·체험·관광지 방문 등 지역 여행 지출을 대상으로 하며, "
                "환급 방식과 한도는 지자체별 세부 공고를 따릅니다."
            ),
        )
    participant_target = (
        record.raw_payload.get("participantTarget") if isinstance(record.raw_payload, dict) else None
    )
    target_lines = _split_detail_lines(participant_target)
    if target_lines:
        for target_line in target_lines:
            _append(detail["applicationTarget"], title="신청대상", description=target_line)
    else:
        _append(
            detail["applicationTarget"],
            title="신청대상",
            description=_local_half_trip_default_target(record),
        )
    _append(
        detail["requiredDocuments"],
        title="필요서류",
        description=(
            "방문·결제·숙박 등 이용 사실을 확인할 수 있는 영수증, 결제내역, "
            "인증사진 등 지자체별 요구 증빙을 준비해야 합니다."
        ),
    )
    _append(
        detail["notes"],
        title="비고",
        description="예산 소진, 신청 인원, 지자체 운영 기준에 따라 조기 종료되거나 세부 조건이 달라질 수 있습니다.",
    )
    _append(
        detail["notes"],
        title="비고",
        description="신청 전 공식 혜택 안내에서 최신 신청 방법, 제출 증빙, 제외 조건을 최종 확인하세요.",
    )


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

    for support_line in _split_detail_lines(payload.get("supportDetail")):
        if support_line.startswith("※") or re.search(r"불가|제외|확인", support_line):
            _append(detail["notes"], title="비고", description=support_line)
        elif re.fullmatch(r"\d+[.)]\s*.+", support_line):
            continue
        elif re.search(r"최대|최소|50%|70%|지급|환급|지원|상품권|소비|금액|만원", support_line):
            _append(detail["supportContent"], title="지원내용", description=support_line)
    for document_line in _split_detail_lines(payload.get("requiredDocumentsDetail")):
        _append(detail["requiredDocuments"], title="필요서류", description=document_line)
    for note_line in _split_detail_lines(payload.get("detailNotes")):
        _append(detail["notes"], title="비고", description=note_line)

    semantic_texts: list[str] = []
    for candidate in [payload.get("notes"), field_values.get("특이사항"), labeled_value("특이사항"), target_condition]:
        for part in re.split(r"\s*(?:,|\*|ㆍ|·|\n|/)\s*", _text(candidate)):
            part = _text(part)
            if part and part not in semantic_texts:
                semantic_texts.append(part)
    for part in semantic_texts:
        payment_document = re.match(r"(.+?결제)한?\s+(.+)$", part)
        if payment_document and re.search(r"영수증|거래내역|결제내역|인증사진|캡처|캡쳐|증빙|서류", payment_document.group(2)):
            _append(detail["supportContent"], title="혜택 적용 조건", description=payment_document.group(1))
            _append(detail["requiredDocuments"], title="필요 서류", description=payment_document.group(2))
        elif re.search(r"공지|고시공고|필독|문의|유의|주의|확인", part):
            _append(detail["notes"], title="비고", description=part)
        elif re.search(r"영수증|거래내역|결제내역|인증사진|캡처|캡쳐|증빙|서류", part) and not re.search(r"방문|결제|이용|사용|가맹점", part):
            _append(detail["requiredDocuments"], title="필요 서류", description=part)
        else:
            _append(detail["supportContent"], title="혜택 적용 조건", description=part)

    for value in currency_values:
        _append(detail["supportContent"], title="혜택 적용 조건", description=f"{value} 사용")

    _append_local_half_trip_default_sections(detail, record=record)

    period_payload = dict(payload)
    if not period_payload.get("applicationPeriod") and period_payload.get("applicationPeriodDetail"):
        period_payload["applicationPeriod"] = period_payload["applicationPeriodDetail"]
    if not period_payload.get("tripPeriod") and period_payload.get("tripPeriodDetail"):
        period_payload["tripPeriod"] = period_payload["tripPeriodDetail"]
    default_year = record.last_fetched_at.year if record.last_fetched_at is not None else 2026
    evidence = evidence_from_payload(period_payload, default_year=default_year, source=record.source_category)
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



def _digital_partner_benefits(payload: dict[str, object]) -> list[dict[str, object]]:
    benefits = payload.get("partnerBenefits")
    if not isinstance(benefits, list):
        return []
    return [benefit for benefit in benefits if isinstance(benefit, dict)]


def _digital_partner_summary(payload: dict[str, object]) -> dict[str, object]:
    summary = payload.get("partnerBenefitSummary")
    return summary if isinstance(summary, dict) else {}


def _digital_partner_category_highlights(payload: dict[str, object]) -> list[dict[str, object]]:
    highlights = payload.get("partnerBenefitCategoryHighlights")
    if not isinstance(highlights, list):
        return []
    return [highlight for highlight in highlights if isinstance(highlight, dict)]


def _digital_partner_summary_description(
    *,
    city: str,
    benefits: list[dict[str, object]],
    payload: dict[str, object],
) -> str:
    summary = _digital_partner_summary(payload)
    total = summary.get("totalCount")
    if not isinstance(total, int):
        total = len(benefits)
    category_counts = summary.get("categoryCounts")
    if not isinstance(category_counts, dict):
        category_counts = dgtour_identity.summarize_partner_benefit_categories(benefits)
    category_text = ", ".join(
        f"{_text(name)} {count}곳"
        for name, count in category_counts.items()
        if _text(name) and isinstance(count, int) and count > 0
    )
    city_text = dgtour_identity.display_city_name(city)
    if total > 0 and category_text:
        return f"{city_text} 제휴처 {total}곳의 숙박, 식음, 체험, 관광지 혜택을 제공합니다. 주요 분야: {category_text}."
    if total > 0:
        return f"{city_text} 제휴처 {total}곳의 디지털관광주민증 혜택을 제공합니다."
    return dgtour_identity.SUPPORT_CONTENT_TEXT


def _append_digital_partner_benefits(
    detail: StructuredDetail,
    *,
    city: str,
    payload: dict[str, object],
) -> None:
    benefits = _digital_partner_benefits(payload)
    if not benefits:
        _append(
            detail["supportContent"],
            title="혜택",
            description=dgtour_identity.SUPPORT_CONTENT_TEXT,
            amount=dgtour_identity.DEFAULT_BENEFIT_VALUE_TEXT,
        )
        return

    _append(
        detail["supportContent"],
        title="핵심 혜택",
        description=_digital_partner_summary_description(
            city=city,
            benefits=benefits,
            payload=payload,
        ),
    )
    highlights = _digital_partner_category_highlights(payload)
    if not highlights:
        highlights = dgtour_identity.partner_benefit_category_highlights(benefits)
    if highlights:
        _append(
            detail["supportContent"],
            title="카테고리별 인기 혜택",
            description="인기순 대표 제휴처와 주요 혜택을 카테고리별로 정리했습니다.",
        )
    for highlight in highlights:
        representative = highlight.get("representative")
        description = dgtour_identity.format_partner_benefit_highlight_for_display(highlight)
        if not description:
            continue
        item = {"title": "카테고리별 인기 혜택", "description": description}
        if isinstance(representative, dict):
            url = dgtour_identity.official_member_benefit_url(representative)
            if url:
                item["url"] = url
        detail["supportContent"].append(item)

def _digital_tourism_resident_card(record: ExternalSourceRecord) -> ExternalSourceSemanticMapping:
    payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    detail = empty_structured_detail()

    city = _text(record.city) or dgtour_identity.city_from_title(_text(record.title))
    _append_digital_partner_benefits(detail, city=city, payload=payload)

    target = dgtour_identity.application_target_text(city)
    _append(detail["applicationTarget"], title="신청대상", description=target)
    _append(
        detail["applicationTarget"],
        title="이용조건",
        description=dgtour_identity.USAGE_CONDITION_TEXT,
    )

    default_year = record.last_fetched_at.year if record.last_fetched_at is not None else 2026
    evidence = evidence_from_payload(payload, default_year=default_year, source=record.source_category)
    for item in structured_period_items(evidence):
        detail["periods"].append(dict(item))

    _append(
        detail["requiredDocuments"],
        title="필요서류",
        description=dgtour_identity.REQUIRED_DOCUMENTS_TEXT,
    )
    payload_notes = payload.get("notes")
    raw_notes = _text(payload_notes) if isinstance(payload_notes, str) else ""
    if raw_notes and not dgtour_identity.contains_forbidden_half_trip_text(raw_notes):
        _append(detail["notes"], title="비고", description=raw_notes)
    _append(detail["notes"], title="비고", description=dgtour_identity.OFFICIAL_CONFIRMATION_NOTE)
    _append(detail["notes"], title="비고", description=dgtour_identity.BENEFIT_VARIATION_NOTE)

    return ExternalSourceSemanticMapping(target, detail, "mapped")


def _island_moment_text(value: object) -> str:
    text = _text(value)
    if text.endswith("T23:59") or text.endswith("T00:00"):
        return text[:10]
    return text.replace("T", " ")


def _island_visit(record: ExternalSourceRecord) -> ExternalSourceSemanticMapping:
    """2026 섬 방문의 해 여행비 지원: screen sections plus the reviewed procedure kept for applicationGuide."""
    payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    procedure = payload.get("procedure")
    if not isinstance(procedure, dict) or not procedure.get("rounds"):
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "invalid")

    detail = empty_structured_detail()
    _append(detail["supportContent"], title="지원 내용", description=_text(record.benefit_text))
    min_payment = procedure.get("minPaymentKrw")
    if isinstance(min_payment, int) and min_payment > 0:
        _append(detail["supportContent"], title="지급 조건", description=f"결제 금액 {min_payment // 10_000}만원 이상 이용자 대상 지급")

    for round_ in procedure["rounds"]:
        if not isinstance(round_, dict) or not round_.get("key"):
            continue
        label = f"{round_['key']}차"
        if round_.get("applyUntil"):
            item: dict[str, object] = {
                "title": f"{label} 신청 기간",
                "description": " ~ ".join(
                    part for part in (_island_moment_text(round_.get("applyStart")), _island_moment_text(round_["applyUntil"])) if part
                ),
                "type": "application",
                "endDate": str(round_["applyUntil"])[:10],
            }
            if round_.get("applyStart"):
                item["startDate"] = str(round_["applyStart"])[:10]
            detail["periods"].append(item)
        if round_.get("travelStart") and round_.get("travelEnd"):
            detail["periods"].append(
                {
                    "title": f"{label} 여행 기간",
                    "description": f"{round_['travelStart']} ~ {round_['travelEnd']}",
                    "startDate": round_["travelStart"],
                    "endDate": round_["travelEnd"],
                    "type": "usage",
                }
            )
    days = procedure.get("documentDeadlineDaysAfterTrip")
    if isinstance(days, int) and days > 0:
        detail["periods"].append(
            {"title": "서류 제출 기한", "description": f"여행 종료 후 {days}일 이내 서류 제출 구글폼으로 제출", "type": "documents"}
        )

    exclusions = [item for item in procedure.get("exclusions") or [] if isinstance(item, str)]
    if any("대표자 1인" in item for item in exclusions):
        _append(detail["applicationTarget"], title="신청 대상", description="1팀(가족, 친구, 모임)별 대표자 1인 1회 신청 (중복 신청 불가)")
    nights = procedure.get("minNights")
    if isinstance(nights, int) and nights > 0:
        _append(
            detail["applicationTarget"],
            title="여행 조건",
            description=f"대상 섬 리스트에 있는, 육지와 연결되지 않아 배로 들어가는 섬에서 {nights}박 {nights + 1}일 이상 체류",
        )
    _append(detail["applicationTarget"], title="숙박", description="섬 내 등록 숙박업소 이용 (호텔, 리조트, 펜션, 민박 등 / 캠핑 가능)")
    if isinstance(min_payment, int) and min_payment > 0:
        _append(detail["applicationTarget"], title="결제 금액", description=f"결제 금액 {min_payment // 10_000}만원 이상")

    for document in procedure.get("requiredDocuments") or []:
        if isinstance(document, str):
            _append(detail["requiredDocuments"], title="필수 증빙", description=document)

    if isinstance(procedure.get("photoRequirement"), str):
        _append(detail["notes"], title="증빙 사진", description=procedure["photoRequirement"])
    for item in exclusions:
        _append(detail["notes"], title="지원 제외", description=item)
    contacts = procedure.get("contacts") if isinstance(procedure.get("contacts"), dict) else {}
    contact_parts = []
    if contacts.get("email"):
        contact_parts.append(f"이메일 {contacts['email']}")
    if contacts.get("phones"):
        contact_parts.append("전화 " + " / ".join(str(phone) for phone in contacts["phones"]))
    if contact_parts:
        _append(detail["notes"], title="문의", description=" · ".join(contact_parts))

    detail["applicationGuide"] = deepcopy(procedure)  # type: ignore[assignment]  # stored with the reviewed policy, projected separately
    return ExternalSourceSemanticMapping(None, detail, "mapped")


_MAPPERS: dict[str, Callable[[ExternalSourceRecord], ExternalSourceSemanticMapping]] = {
    "island_visit": _island_visit,
    "local_half_trip": _local_half_trip,
    dgtour_identity.SOURCE_CATEGORY: _digital_tourism_resident_card,
    "stay_discount": _stay_discount,
}


def map_external_source_semantics(record: ExternalSourceRecord) -> ExternalSourceSemanticMapping:
    mapper = _MAPPERS.get(record.source_category or "")
    if mapper is None:
        return ExternalSourceSemanticMapping(None, empty_structured_detail(), "missing")
    return mapper(record)
