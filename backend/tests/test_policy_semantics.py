from __future__ import annotations

from types import SimpleNamespace

from app.models.policy_status import (
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_HIDDEN,
    is_active_policy_status,
    is_hidden_policy_status,
    is_public_policy_status,
    normalize_policy_status,
)
from app.services.policy_semantics import (
    PolicySourceIdentity,
    api_policy_source_type,
    api_policy_source_type_for_identity,
    api_policy_source_type_for_policy,
    benefit_display_amount,
    benefit_display_amount_for_policy,
    format_benefit_amount,
    is_active_policy,
    is_hidden_policy,
    is_public_policy,
    policy_status,
    policy_url_fields,
    policy_url_fields_for_policy,
    requirement_items_for_policy,
    requirement_items_from_target_condition,
    safe_policy_url,
)


def test_policy_status_constants_and_predicates_preserve_legacy_active_default() -> None:
    assert POLICY_STATUS_ACTIVE == "active"
    assert POLICY_STATUS_HIDDEN == "hidden"
    assert normalize_policy_status(None) == "active"
    assert normalize_policy_status("") == "active"
    assert is_active_policy_status(None) is True
    assert is_public_policy_status("active") is True
    assert is_public_policy_status("hidden") is False
    assert is_hidden_policy_status("hidden") is True


def test_policy_object_status_helpers_do_not_require_model_imports() -> None:
    active_policy = SimpleNamespace(status="active")
    hidden_policy = SimpleNamespace(status="hidden")
    legacy_policy = SimpleNamespace()

    assert policy_status(legacy_policy) == "active"
    assert is_active_policy(active_policy) is True
    assert is_public_policy(active_policy) is True
    assert is_hidden_policy(active_policy) is False
    assert is_public_policy(hidden_policy) is False
    assert is_hidden_policy(hidden_policy) is True


def test_benefit_display_amount_prefers_detail_then_formatted_amount_then_empty() -> None:
    assert format_benefit_amount(300000) == "최대 30만원"
    assert format_benefit_amount(12345) == "최대 12,345원"
    assert format_benefit_amount(None) is None
    assert benefit_display_amount(benefit_detail="상세 혜택", benefit_amount=300000) == "상세 혜택"
    assert benefit_display_amount(benefit_detail=None, benefit_amount=300000) == "최대 30만원"
    assert benefit_display_amount(benefit_detail=None, benefit_amount=None) == ""


def test_benefit_display_amount_for_policy_hides_legacy_column_names() -> None:
    policy = SimpleNamespace(benefit_detail=None, benefit_amount=70000)

    assert benefit_display_amount_for_policy(policy) == "최대 7만원"


def test_requirement_items_split_and_sanitize_target_condition() -> None:
    assert requirement_items_from_target_condition(
        "국내 거주자\n숙박 영수증 제출\n문의전화 1660-3067\n모바일 앱 신청"
    ) == ["국내 거주자", "숙박 영수증 제출", "모바일 앱 신청"]
    assert requirement_items_from_target_condition(None) == []


def test_requirement_items_for_policy_hides_target_condition_column_name() -> None:
    policy = SimpleNamespace(target_condition="1660-3067\n국내 거주자")

    assert requirement_items_for_policy(policy) == ["국내 거주자"]


def test_policy_url_fields_preserve_apply_and_official_urls_separately() -> None:
    urls = policy_url_fields(
        apply_url="https://apply.example/policy",
        official_url="https://official.example/policy",
    )

    assert urls == {
        "applyUrl": "https://apply.example/policy",
        "officialUrl": "https://official.example/policy",
    }


def test_policy_url_fields_omit_unsafe_urls_at_semantic_boundary() -> None:
    assert safe_policy_url("https://safe.example/policy") == "https://safe.example/policy"
    assert safe_policy_url("http://safe.example/policy") == "http://safe.example/policy"
    assert safe_policy_url("javascript:alert(1)") is None
    assert safe_policy_url("https:///missing-host") is None
    assert safe_policy_url("") is None

    urls = policy_url_fields(
        apply_url="javascript:alert(1)",
        official_url="https:///missing-host",
    )

    assert urls == {"applyUrl": None, "officialUrl": None}


def test_policy_url_fields_for_policy_hides_url_column_names() -> None:
    policy = SimpleNamespace(
        apply_url="https://apply.example/policy",
        official_url="https://official.example/policy",
    )

    assert policy_url_fields_for_policy(policy) == {
        "applyUrl": "https://apply.example/policy",
        "officialUrl": "https://official.example/policy",
    }


def test_api_policy_source_type_preserves_fallback_rule() -> None:
    assert api_policy_source_type(source_type="official_campaign", external_source_record_id=None) == "external"
    assert api_policy_source_type(source_type="legacy_source", external_source_record_id=None) == "external"
    assert api_policy_source_type(source_type="INTERNAL", external_source_record_id=None) == "internal"
    assert api_policy_source_type(source_type="external", external_source_record_id=None) == "external"
    assert api_policy_source_type(source_type="", external_source_record_id=None) == "internal"
    assert api_policy_source_type(source_type=None, external_source_record_id=None) == "internal"
    assert api_policy_source_type(source_type="internal", external_source_record_id=7) == "external"


def test_policy_source_identity_supports_policy_and_api_style_mappings() -> None:
    policy = SimpleNamespace(
        source_type="official_campaign",
        external_source_record_id=7,
        source_name="official external benefits",
        source_category="local_half_trip",
    )

    identity = PolicySourceIdentity.from_policy(policy)

    assert identity.as_dict() == {
        "source_type": "official_campaign",
        "external_source_record_id": 7,
        "source_name": "official external benefits",
        "source_category": "local_half_trip",
    }
    assert api_policy_source_type_for_identity(identity) == "external"
    assert api_policy_source_type_for_policy(policy) == "external"

    api_identity = PolicySourceIdentity.from_mapping(
        {
            "sourceType": "INTERNAL",
            "externalSourceRecordId": None,
            "sourceName": "seed",
            "sourceCategory": "digital_tourism_card",
        }
    )
    assert api_identity.source_type == "INTERNAL"
    assert api_identity.source_name == "seed"
    assert api_policy_source_type_for_identity(api_identity) == "internal"


def test_policy_semantics_module_stays_below_policy_service_boundaries() -> None:
    import ast
    from pathlib import Path

    module_path = Path(__file__).parents[1] / "app" / "services" / "policy_semantics.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)

    forbidden = {
        "app.services.policies",
        "app.services.policy_structured_detail",
        "app.services.policy_normalization",
        "app.api.routes.policies",
        "app.repositories.policies",
    }
    assert imported_modules.isdisjoint(forbidden)
