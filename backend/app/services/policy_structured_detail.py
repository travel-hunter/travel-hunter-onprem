from __future__ import annotations

from datetime import date
from typing import Any

from app.models import Policy
from app.services.policy_semantics import (
    benefit_display_amount_for_policy,
    requirement_items_for_policy,
    safe_policy_url,
)


STRUCTURED_DETAIL_SECTION_KEYS = (
    "supportContent",
    "periods",
    "applicationTarget",
    "requiredDocuments",
    "notes",
)
LEGACY_STRUCTURED_DETAIL_SECTION_ALIASES = {
    "supportContent": ("supportContent", "benefits"),
    "periods": ("periods",),
    "applicationTarget": ("applicationTarget", "conditions"),
    "requiredDocuments": ("requiredDocuments", "documents"),
    "notes": ("notes", "notices"),
}
STRUCTURED_DETAIL_ITEM_KEYS = {
    "title",
    "label",
    "description",
    "amount",
    "value",
    "url",
    "startDate",
    "endDate",
    "type",
}


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split())


def _date_text(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _has_text(value: str | None) -> bool:
    return bool(_clean_text(value))


def _safe_url(value: object) -> str | None:
    return safe_policy_url(_clean_text(value))


def empty_structured_detail() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in STRUCTURED_DETAIL_SECTION_KEYS}


def is_effectively_empty_structured_detail(value: object) -> bool:
    if not isinstance(value, dict):
        return True
    for key in STRUCTURED_DETAIL_SECTION_KEYS:
        section = value.get(key)
        if isinstance(section, list) and len(section) > 0:
            return False
    return True


def normalize_structured_detail(value: object) -> dict[str, list[dict[str, Any]]] | None:
    """Return a screen-safe structured detail object or None for fallback rendering."""
    if not isinstance(value, dict):
        return None

    normalized = empty_structured_detail()
    for key in STRUCTURED_DETAIL_SECTION_KEYS:
        raw_items = None
        for alias in LEGACY_STRUCTURED_DETAIL_SECTION_ALIASES[key]:
            candidate = value.get(alias)
            if isinstance(candidate, list):
                raw_items = candidate
                break
        if not isinstance(raw_items, list):
            continue
        cleaned_items: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            cleaned_item: dict[str, str] = {}
            for item_key, item_value in item.items():
                key_text = str(item_key)
                if key_text not in STRUCTURED_DETAIL_ITEM_KEYS:
                    continue
                if key_text == "url":
                    safe_url = _safe_url(item_value)
                    if safe_url is not None:
                        cleaned_item[key_text] = safe_url
                    continue
                text = _clean_text(item_value)
                if text:
                    cleaned_item[key_text] = text
            if cleaned_item:
                cleaned_items.append(cleaned_item)
        normalized[key] = cleaned_items

    if is_effectively_empty_structured_detail(normalized):
        return None
    return normalized


def _reviewed_period_item(
    value: object,
    *,
    title: str,
    period_type: str,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    item: dict[str, Any] = {"title": title, "type": period_type}
    conclusion = _clean_text(value.get("conclusion"))
    if conclusion:
        item["description"] = conclusion
    for source_key, output_key in (("startDate", "startDate"), ("endDate", "endDate")):
        date_value = _clean_text(value.get(source_key))
        if date_value:
            item[output_key] = date_value
    return item if len(item) > 2 else None


def _reviewed_evidence_detail_for_api(
    policy: Policy,
) -> dict[str, list[dict[str, Any]]] | None:
    """Project reviewed evidence into the existing public structured-detail DTO.

    The reconciliation manifest intentionally stores review metadata separately from
    the screen DTO. This adapter keeps those DB bytes intact while exposing only the
    already-supported list sections and typed application/usage periods.
    """
    value = policy.structured_detail
    if not isinstance(value, dict) or not any(
        key in value for key in ("applicationPeriod", "usagePeriod")
    ):
        return None

    detail = build_structured_detail_from_policy(policy)
    detail["periods"] = []
    application = _reviewed_period_item(
        value.get("applicationPeriod"),
        title="신청 기간",
        period_type="application",
    )
    usage = _reviewed_period_item(
        value.get("usagePeriod"),
        title="여행 기간",
        period_type="usage",
    )
    if application is not None:
        detail["periods"].append(application)
    if usage is not None:
        detail["periods"].append(usage)
    return normalize_structured_detail(detail)


def build_structured_detail_from_policy(policy: Policy) -> dict[str, list[dict[str, Any]]]:
    """Build a loose, non-inventive structured detail from current Policy fields."""
    detail = empty_structured_detail()

    benefit_description = _clean_text(policy.benefit_detail or policy.policy_comment or policy.description)
    if benefit_description:
        benefit_item: dict[str, Any] = {
            "title": "혜택",
            "description": benefit_description,
        }
        benefit_amount = benefit_display_amount_for_policy(policy)
        if benefit_amount:
            benefit_item["amount"] = _clean_text(benefit_amount)
        detail["supportContent"].append(benefit_item)

    requirements = requirement_items_for_policy(policy)
    detail["applicationTarget"].extend(
        {"title": "조건", "description": requirement}
        for requirement in requirements
    )

    period_item: dict[str, Any] = {}
    if _has_text(policy.policy_period):
        period_item = {"title": "기간", "description": _clean_text(policy.policy_period)}
    elif policy.start_date is not None or policy.end_date is not None:
        start_date = _date_text(policy.start_date)
        end_date = _date_text(policy.end_date)
        description = " ~ ".join(value for value in [start_date, end_date] if value)
        period_item = {"title": "신청 기간", "description": description}
        if start_date:
            period_item["startDate"] = start_date
        if end_date:
            period_item["endDate"] = end_date
    if period_item:
        detail["periods"].append(period_item)


    detail["requiredDocuments"].extend(
        {"title": "필요 서류", "description": document.document_name}
        for document in policy.documents
        if _has_text(document.document_name)
    )

    if _has_text(policy.policy_comment) and policy.policy_comment != policy.benefit_detail:
        detail["notes"].append({"title": "비고", "description": _clean_text(policy.policy_comment)})

    return detail


def structured_detail_for_api(policy: Policy) -> dict[str, list[dict[str, Any]]] | None:
    reviewed_detail = _reviewed_evidence_detail_for_api(policy)
    if reviewed_detail is not None:
        return reviewed_detail
    return normalize_structured_detail(policy.structured_detail)
