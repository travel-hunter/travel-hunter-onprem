from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, cast
from urllib.parse import urlparse

from app.models.policy_status import (
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_HIDDEN,
    is_active_policy_status,
    is_hidden_policy_status,
    is_public_policy_status,
    normalize_policy_status,
)
from app.services.policy_requirements import (
    sanitize_requirement_items,
    split_requirement_lines,
)

ApiPolicySourceType = Literal["internal", "external"]
API_POLICY_SOURCE_TYPES = frozenset({"internal", "external"})
SAFE_POLICY_URL_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True, slots=True)
class PolicySourceIdentity:
    """Source fields that determine a public policy DTO's source identity.

    The constructor helpers intentionally keep legacy DB/source column names at this
    boundary so service/repository/trip code can depend on semantic names later.
    """

    source_type: str | None = None
    external_source_record_id: Any | None = None
    source_name: str | None = None
    source_category: str | None = None

    @classmethod
    def from_policy(cls, policy: Any) -> PolicySourceIdentity:
        return cls(
            source_type=getattr(policy, "source_type", None),
            external_source_record_id=getattr(policy, "external_source_record_id", None),
            source_name=getattr(policy, "source_name", None),
            source_category=getattr(policy, "source_category", None),
        )

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> PolicySourceIdentity:
        return cls(
            source_type=value.get("sourceType", value.get("source_type")),
            external_source_record_id=value.get(
                "externalSourceRecordId",
                value.get("external_source_record_id"),
            ),
            source_name=value.get("sourceName", value.get("source_name")),
            source_category=value.get("sourceCategory", value.get("source_category")),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def policy_status(policy: Any) -> str:
    return normalize_policy_status(getattr(policy, "status", None))


def is_active_policy(policy: Any) -> bool:
    return is_active_policy_status(getattr(policy, "status", None))


def is_hidden_policy(policy: Any) -> bool:
    return is_hidden_policy_status(getattr(policy, "status", None))


def is_public_policy(policy: Any) -> bool:
    return is_public_policy_status(getattr(policy, "status", None))


def format_benefit_amount(value: int | None) -> str | None:
    if value is None:
        return None
    if value >= 10000 and value % 10000 == 0:
        return f"최대 {value // 10000}만원"
    return f"최대 {value:,}원"


def benefit_display_amount(
    *,
    benefit_detail: str | None,
    benefit_amount: int | None,
) -> str:
    return benefit_detail or format_benefit_amount(benefit_amount) or ""


def benefit_display_amount_for_policy(policy: Any) -> str:
    return benefit_display_amount(
        benefit_detail=getattr(policy, "benefit_detail", None),
        benefit_amount=getattr(policy, "benefit_amount", None),
    )


def requirement_items_from_target_condition(target_condition: str | None) -> list[str]:
    return sanitize_requirement_items(split_requirement_lines(target_condition))


def requirement_items_for_policy(policy: Any) -> list[str]:
    return requirement_items_from_target_condition(getattr(policy, "target_condition", None))


def safe_policy_url(value: str | None) -> str | None:
    if value is None:
        return None
    url = value.strip()
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme.lower() not in SAFE_POLICY_URL_SCHEMES or not parsed.netloc:
        return None
    return url


def policy_url_fields(
    *,
    apply_url: str | None,
    official_url: str | None,
) -> dict[str, str | None]:
    return {
        "applyUrl": safe_policy_url(apply_url),
        "officialUrl": safe_policy_url(official_url),
    }


def policy_url_fields_for_policy(policy: Any) -> dict[str, str | None]:
    return policy_url_fields(
        apply_url=getattr(policy, "apply_url", None),
        official_url=getattr(policy, "official_url", None),
    )


def api_policy_source_type(
    *,
    source_type: str | None,
    external_source_record_id: Any | None,
) -> ApiPolicySourceType:
    if external_source_record_id is not None:
        return "external"
    normalized_source_type = (source_type or "internal").lower()
    if normalized_source_type in API_POLICY_SOURCE_TYPES:
        return cast(ApiPolicySourceType, normalized_source_type)
    return "external"


def api_policy_source_type_for_identity(
    source_identity: PolicySourceIdentity,
) -> ApiPolicySourceType:
    return api_policy_source_type(
        source_type=source_identity.source_type,
        external_source_record_id=source_identity.external_source_record_id,
    )


def api_policy_source_type_for_policy(policy: Any) -> ApiPolicySourceType:
    return api_policy_source_type_for_identity(PolicySourceIdentity.from_policy(policy))


__all__ = [
    "API_POLICY_SOURCE_TYPES",
    "POLICY_STATUS_ACTIVE",
    "POLICY_STATUS_HIDDEN",
    "SAFE_POLICY_URL_SCHEMES",
    "ApiPolicySourceType",
    "PolicySourceIdentity",
    "api_policy_source_type",
    "api_policy_source_type_for_identity",
    "api_policy_source_type_for_policy",
    "benefit_display_amount",
    "benefit_display_amount_for_policy",
    "format_benefit_amount",
    "is_active_policy",
    "is_hidden_policy",
    "is_public_policy",
    "policy_status",
    "policy_url_fields",
    "policy_url_fields_for_policy",
    "requirement_items_for_policy",
    "requirement_items_from_target_condition",
    "safe_policy_url",
]
