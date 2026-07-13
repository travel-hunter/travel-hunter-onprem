from __future__ import annotations

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExternalSourceRecord, Policy
from app.repositories import external_sources as external_source_repository
from app.services.policies import _external_policy_category
from app.services.policy_structured_detail import build_structured_detail_from_policy
from app.services.travelmonth_normalizer import extract_benefit_value


DEFAULT_TARGET_CONDITION = "공식 혜택 안내에서 조건을 확인하세요."
LOCAL_HALF_TRIP_SOURCE_CATEGORY = "local_half_trip"
CONTACT_ONLY_PATTERN = re.compile(
    r"^\s*(?:문의전화|문의|전화|tel|contact|고객센터|운영사무국)?\s*[:：-]?\s*"
    r"(?:\+?\d[\d\s().-]{5,}\d)\s*$",
    re.IGNORECASE,
)
CONTACT_HINT_PATTERN = re.compile(r"문의|전화|tel|contact|고객센터|운영사무국", re.IGNORECASE)
CONTACT_NUMBER_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{5,}\d)")
CONDITION_HINT_PATTERN = re.compile(
    r"특이사항|조건|인증|방문|결제|가맹점|지역화폐|제로페이|상품|예약|쿠폰|할인|환급|지원|사용|이용|대상|숙박|식사|체험"
)
DOCUMENT_HINT_PATTERN = re.compile(r"영수증|거래내역|결제내역|인증사진|캡처|캡쳐|증빙|서류")
NOTICE_HINT_PATTERN = re.compile(r"공지|고시공고|필독|문의|유의|주의|확인")
LOCAL_HALF_TRIP_CONDITION_FIELDS = ("특이사항", "지역화폐", "신청조건", "사용조건", "이용조건")
RAW_DETAIL_FIELD_LABELS = (
    "문의전화",
    "문의",
    "전화",
    "연락처",
    "특이사항",
    "지역화폐",
    "신청조건",
    "사용조건",
    "이용조건",
)


@dataclass(frozen=True)
class PolicyPromotionResult:
    promoted_count: int


@dataclass(frozen=True)
class LocalHalfTripStructuredRules:
    """Source-specific field map for building screen-ready local_half_trip sections."""

    condition_fields: tuple[str, ...]
    raw_detail_field_labels: tuple[str, ...]
    semantic_payload_key: str
    currency_payload_key: str
    application_period_payload_key: str
    trip_period_payload_key: str


LOCAL_HALF_TRIP_STRUCTURED_RULES = LocalHalfTripStructuredRules(
    condition_fields=LOCAL_HALF_TRIP_CONDITION_FIELDS,
    raw_detail_field_labels=RAW_DETAIL_FIELD_LABELS,
    semantic_payload_key="notes",
    currency_payload_key="localCurrency",
    application_period_payload_key="applicationPeriod",
    trip_period_payload_key="tripPeriod",
)
RAW_DETAIL_FIELD_LABEL_PATTERN = "|".join(
    re.escape(label) for label in LOCAL_HALF_TRIP_STRUCTURED_RULES.raw_detail_field_labels
)


def _normalized_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _is_contact_only_text(value: str) -> bool:
    text = _normalized_text(value)
    if not text:
        return False
    return bool(CONTACT_ONLY_PATTERN.match(text))


def _is_condition_candidate(value: str) -> bool:
    text = _normalized_text(value)
    if not text:
        return False
    if _is_contact_only_text(text):
        return False
    if CONTACT_NUMBER_PATTERN.search(text):
        return False
    if CONTACT_HINT_PATTERN.search(text) and not CONDITION_HINT_PATTERN.search(text):
        return False
    return bool(CONDITION_HINT_PATTERN.search(text))


def _raw_field_value(record: ExternalSourceRecord, field_name: str) -> str:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    field_values = raw_payload.get("field_values")
    if not isinstance(field_values, dict):
        return ""
    return _normalized_text(field_values.get(field_name))


def _raw_detail_field_value(record: ExternalSourceRecord, field_name: str) -> str:
    raw_detail_text = _normalized_text(record.raw_detail_text)
    if not raw_detail_text:
        return ""
    match = re.search(
        rf"(?:^|\s){re.escape(field_name)}\s*[:：-]\s*(.*?)(?=\s*(?:{RAW_DETAIL_FIELD_LABEL_PATTERN})\s*[:：-]|$)",
        raw_detail_text,
    )
    if not match:
        return ""
    return _normalized_text(match.group(1))


def _safe_unlabeled_raw_detail_condition(record: ExternalSourceRecord) -> str:
    raw_detail_text = _normalized_text(record.raw_detail_text)
    if not raw_detail_text:
        return ""
    if (
        CONTACT_HINT_PATTERN.search(raw_detail_text)
        or CONTACT_NUMBER_PATTERN.search(raw_detail_text)
    ):
        return ""
    return raw_detail_text


def _local_half_trip_target_condition(record: ExternalSourceRecord) -> str:
    candidates = [
        *(
            _raw_field_value(record, field_name)
            for field_name in LOCAL_HALF_TRIP_STRUCTURED_RULES.condition_fields
        ),
        *(
            _raw_detail_field_value(record, field_name)
            for field_name in LOCAL_HALF_TRIP_STRUCTURED_RULES.condition_fields
        ),
        _safe_unlabeled_raw_detail_condition(record),
    ]
    for candidate in candidates:
        if _is_condition_candidate(candidate):
            return candidate
    return DEFAULT_TARGET_CONDITION


def _target_condition_for_record(record: ExternalSourceRecord) -> str:
    if record.source_category == LOCAL_HALF_TRIP_SOURCE_CATEGORY:
        return _local_half_trip_target_condition(record)
    contact_text = _normalized_text(record.contact_text)
    if contact_text and not _is_contact_only_text(contact_text):
        return contact_text
    return DEFAULT_TARGET_CONDITION


def _append_structured_item(
    target: list[dict[str, str]],
    *,
    title: str,
    description: str,
) -> None:
    text = _normalized_text(description)
    if not text:
        return
    if any(item.get("description") == text for item in target):
        return
    target.append({"title": title, "description": text})


def _split_local_half_trip_condition_text(value: str) -> list[str]:
    items: list[str] = []
    for item in re.split(r"\s*(?:,|\*|ㆍ|·|\n|/)\s*", value):
        text = _normalized_text(item)
        if text:
            items.append(text)
    return items


def _append_local_half_trip_semantic_part(
    detail: dict[str, list[dict[str, str]]],
    value: str,
) -> None:
    item = _normalized_text(value)
    if not item:
        return

    if item == DEFAULT_TARGET_CONDITION:
        _append_structured_item(detail["conditions"], title="조건", description=item)
        return

    payment_document_match = re.match(r"(.+?결제)한?\s+(.+)$", item)
    if payment_document_match and DOCUMENT_HINT_PATTERN.search(payment_document_match.group(2)):
        _append_structured_item(
            detail["conditions"],
            title="혜택 적용 조건",
            description=payment_document_match.group(1),
        )
        _append_structured_item(
            detail["documents"],
            title="필요 서류",
            description=payment_document_match.group(2),
        )
        return

    if NOTICE_HINT_PATTERN.search(item):
        _append_structured_item(detail["notices"], title="확인 필요 사항", description=item)
        return

    if DOCUMENT_HINT_PATTERN.search(item) and not re.search(r"방문|결제|이용|사용|가맹점", item):
        _append_structured_item(detail["documents"], title="필요 서류", description=item)
        return

    _append_structured_item(detail["conditions"], title="혜택 적용 조건", description=item)


def _raw_payload_text(record: ExternalSourceRecord, key: str) -> str:
    raw_payload = record.raw_payload if isinstance(record.raw_payload, dict) else {}
    return _normalized_text(raw_payload.get(key))


def _local_half_trip_semantic_source_texts(record: ExternalSourceRecord, policy: Policy) -> list[str]:
    candidates = [
        _raw_payload_text(record, LOCAL_HALF_TRIP_STRUCTURED_RULES.semantic_payload_key),
        _raw_field_value(record, "특이사항"),
        _raw_detail_field_value(record, "특이사항"),
        policy.target_condition,
    ]
    texts: list[str] = []
    for candidate in candidates:
        for item in _split_local_half_trip_condition_text(candidate or ""):
            if item and item not in texts:
                texts.append(item)
    return texts


def _local_half_trip_currency_texts(record: ExternalSourceRecord) -> list[str]:
    candidates = [
        _raw_payload_text(record, LOCAL_HALF_TRIP_STRUCTURED_RULES.currency_payload_key),
        _raw_field_value(record, "지역화폐"),
        _raw_detail_field_value(record, "지역화폐"),
    ]
    texts: list[str] = []
    for candidate in candidates:
        text = _normalized_text(candidate)
        if text and text not in texts:
            texts.append(text)
    return texts


def _append_local_half_trip_periods(
    detail: dict[str, list[dict[str, object]]],
    record: ExternalSourceRecord,
) -> None:
    period_items: list[dict[str, str]] = []
    application_period = _raw_payload_text(
        record,
        LOCAL_HALF_TRIP_STRUCTURED_RULES.application_period_payload_key,
    )
    if application_period:
        _append_structured_item(
            period_items,
            title="신청 기간",
            description=f"신청 기간: {application_period}",
        )
    trip_period = _raw_payload_text(
        record,
        LOCAL_HALF_TRIP_STRUCTURED_RULES.trip_period_payload_key,
    )
    if trip_period:
        _append_structured_item(
            period_items,
            title="여행 기간",
            description=f"여행 기간: {trip_period}",
        )
    if period_items:
        detail["periods"] = period_items


def _build_local_half_trip_structured_detail(
    policy: Policy,
    record: ExternalSourceRecord,
) -> dict[str, list[dict[str, object]]]:
    detail = build_structured_detail_from_policy(policy)
    parsed_detail: dict[str, list[dict[str, str]]] = {
        "conditions": [],
        "documents": [],
        "notices": [],
    }
    for item in _local_half_trip_semantic_source_texts(record, policy):
        _append_local_half_trip_semantic_part(parsed_detail, item)
    for item in _local_half_trip_currency_texts(record):
        _append_structured_item(
            parsed_detail["conditions"],
            title="혜택 적용 조건",
            description=f"{item} 사용",
        )

    for section in ("conditions", "documents", "notices"):
        detail[section] = parsed_detail[section]
    _append_local_half_trip_periods(detail, record)
    return detail


def _build_structured_detail_for_record(
    policy: Policy,
    record: ExternalSourceRecord,
) -> dict[str, list[dict[str, object]]]:
    if record.source_category == LOCAL_HALF_TRIP_SOURCE_CATEGORY:
        return _build_local_half_trip_structured_detail(policy, record)
    return build_structured_detail_from_policy(policy)


def _policy_slug_for_external_record(record: ExternalSourceRecord) -> str:
    return f"{external_source_repository.EXTERNAL_POLICY_SLUG_PREFIX}{record.id}"


def _get_policy_for_external_record(
    db: Session,
    record: ExternalSourceRecord,
) -> Policy | None:
    if record.id is not None:
        by_source_record = db.scalar(
            select(Policy).where(Policy.external_source_record_id == record.id)
        )
        if by_source_record is not None:
            return by_source_record
    return db.scalar(select(Policy).where(Policy.slug == _policy_slug_for_external_record(record)))


def _assign_policy_from_external_record(
    policy: Policy,
    record: ExternalSourceRecord,
) -> Policy:
    policy.status = "active"
    if getattr(policy, "admin_override_enabled", False) is True:
        policy.source_type = record.source_type
        policy.source_name = record.source_name
        policy.source_category = record.source_category
        policy.external_source_record_id = record.id
        policy.source_url = record.detail_url or record.collected_page_url or record.source_url
        policy.source_canonical_key = record.canonical_key
        policy.normalized_at = record.last_fetched_at
        policy.last_verified_at = record.last_verified_at
        policy.verification_status = record.freshness_status
        return policy

    benefit_value = extract_benefit_value(record.benefit_text or "", title=record.title)
    benefit_detail = record.benefit_value_text or benefit_value.value_text or record.benefit_text
    policy.slug = _policy_slug_for_external_record(record)
    policy.title = record.title
    policy.organization = record.organizer_text or record.source_name
    policy.policy_type = _external_policy_category(record)
    policy.description = record.raw_detail_text or record.benefit_text
    policy.benefit_amount = record.extracted_amount_krw or benefit_value.amount_krw
    policy.benefit_detail = benefit_detail
    policy.target_condition = _target_condition_for_record(record)
    policy.region = record.region or "전국"
    policy.start_date = record.start_date
    policy.end_date = record.end_date
    policy.official_url = record.detail_url or record.collected_page_url
    policy.apply_url = None
    policy.policy_comment = record.benefit_text[:300] if record.benefit_text else None
    policy.policy_period = None
    policy.source_type = record.source_type
    policy.source_name = record.source_name
    policy.source_category = record.source_category
    policy.external_source_record_id = record.id
    policy.source_url = record.detail_url or record.collected_page_url or record.source_url
    policy.source_canonical_key = record.canonical_key
    policy.normalized_at = record.last_fetched_at
    policy.last_verified_at = record.last_verified_at
    policy.verification_status = record.freshness_status
    policy.structured_detail = _build_structured_detail_for_record(policy, record)
    return policy


def _hide_policy_for_external_record(
    db: Session,
    record: ExternalSourceRecord,
) -> bool:
    policy = _get_policy_for_external_record(db, record)
    if policy is None:
        return False
    policy.status = "hidden"
    policy.source_type = record.source_type
    policy.source_name = record.source_name
    policy.source_category = record.source_category
    policy.external_source_record_id = record.id
    policy.source_url = record.detail_url or record.collected_page_url or record.source_url
    policy.source_canonical_key = record.canonical_key
    policy.normalized_at = record.last_fetched_at
    policy.last_verified_at = record.last_verified_at
    policy.verification_status = record.freshness_status
    return True


def promote_external_benefits_to_policies(db: Session) -> PolicyPromotionResult:
    records = external_source_repository.list_policy_promotion_records(db)
    promoted_count = 0
    promoted_categories: set[str] = set()
    for record in records:
        policy = _get_policy_for_external_record(db, record)
        if policy is None:
            policy = Policy()
            db.add(policy)
        _assign_policy_from_external_record(policy, record)
        promoted_categories.add(record.source_category)
        promoted_count += 1
    for record in external_source_repository.list_policy_deactivation_records(db):
        _hide_policy_for_external_record(db, record)
    if "local_half_trip" in promoted_categories:
        _hide_legacy_dgtour_seed_policies(db)
    db.flush()
    return PolicyPromotionResult(promoted_count=promoted_count)


def _hide_legacy_dgtour_seed_policies(db: Session) -> None:
    legacy_policies = db.scalars(
        select(Policy).where(Policy.slug.like("dgtour-%"))
    ).all()
    for policy in legacy_policies:
        policy.status = "hidden"
