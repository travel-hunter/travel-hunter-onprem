"""island_visit semantic mapping, the applicationGuide projection, and the procedure-aware evidence fingerprint."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.models import ExternalSourceRecord, Policy
from app.services.policy_card_quality import card_copy_for_record

FIXTURE = Path(__file__).parent / "fixtures" / "island_visit_promotion2_2026-09-14.html"
ROUND2_APPLY_FORM = "https://forms.gle/HWrxX3iwEUrciZey6"


def island_record(**overrides) -> ExternalSourceRecord:
    from app.services.island_visit_parser import parse_island_visit_support

    source = parse_island_visit_support(
        FIXTURE.read_text(encoding="utf-8"), fetched_at=datetime(2026, 9, 14, tzinfo=UTC), today=date(2026, 9, 14)
    )[0]
    values = dict(
        id=81,
        source_name=source.source_name,
        source_type=source.source_type,
        source_url=source.source_url,
        source_category=source.source_category,
        external_id=source.external_id,
        canonical_key=source.canonical_key,
        logical_key=source.logical_key,
        collected_page_url=source.collected_page_url,
        title=source.title,
        organizer_text=source.organizer_text,
        organizers=source.organizers,
        region=source.region,
        city=None,
        is_nationwide=True,
        status=source.status,
        start_date=source.start_date,
        end_date=source.end_date,
        benefit_text=source.benefit_text,
        benefit_value_text=source.benefit_value_text,
        extracted_amount_krw=source.extracted_amount_krw,
        benefit_value_type=source.benefit_value_type,
        tags=source.tags,
        inferred_travel_styles=[],
        confidence=source.confidence,
        field_completeness=source.field_completeness,
        raw_list_text=source.raw_list_text,
        raw_detail_text=source.raw_detail_text,
        raw_payload=source.raw_payload,
        last_fetched_at=datetime(2026, 9, 14, tzinfo=UTC),
        freshness_status="fresh",
    )
    values.update(overrides)
    return ExternalSourceRecord(**values)


def _descriptions(detail: dict, section: str) -> list[str]:
    return [str(item["description"]) for item in detail[section]]


# --- mapper ------------------------------------------------------------------------------------


def test_island_mapper_fills_the_five_sections_and_keeps_the_procedure() -> None:
    from app.services.policy_semantic_mapping import map_external_source_semantics
    from app.services.policy_structured_detail import STRUCTURED_DETAIL_SECTION_KEYS, normalize_structured_detail

    record = island_record()
    result = map_external_source_semantics(record)
    detail = result.structured_detail

    assert result.mapper_status == "mapped"
    assert detail["applicationGuide"] == record.raw_payload["procedure"]
    assert any(text.startswith("여행비 10만원") for text in _descriptions(detail, "supportContent"))
    assert [(item["title"], item.get("startDate"), item.get("endDate"), item.get("type")) for item in detail["periods"]] == [
        ("1차 신청 기간", "2026-06-17", "2026-06-30", "application"),
        ("1차 여행 기간", "2026-07-01", "2026-08-31", "usage"),
        ("2차 신청 기간", None, "2026-09-21", "application"),
        ("2차 여행 기간", "2026-10-01", "2026-11-04", "usage"),
        ("서류 제출 기한", None, None, "documents"),
    ]
    assert "여행 종료 후 14일 이내" in detail["periods"][-1]["description"]
    target = " ".join(_descriptions(detail, "applicationTarget"))
    for phrase in ("대표자 1인", "1박 2일 이상", "등록 숙박업소", "10만원 이상"):
        assert phrase in target
    assert _descriptions(detail, "requiredDocuments") == record.raw_payload["procedure"]["requiredDocuments"]
    notes = " ".join(_descriptions(detail, "notes"))
    for phrase in ("법인 카드 사용 불가", "주민등록번호", "info@visitisland.kr", "070-4337-5058"):
        assert phrase in notes

    normalized = normalize_structured_detail(detail)
    assert set(normalized) == set(STRUCTURED_DETAIL_SECTION_KEYS)  # public structuredDetail contract unchanged


def test_island_mapper_without_procedure_is_invalid_not_empty() -> None:
    from app.services.policy_semantic_mapping import map_external_source_semantics

    result = map_external_source_semantics(island_record(raw_payload={"applicationPeriod": "x"}))
    assert result.mapper_status == "invalid"
    assert "applicationGuide" not in result.structured_detail


# --- applicationGuide projection ------------------------------------------------------------------


def _guide(today: date):
    from app.services.island_application_guide import application_guide_for_api
    from app.services.policy_semantic_mapping import map_external_source_semantics

    return application_guide_for_api(map_external_source_semantics(island_record()).structured_detail, today=today)


def test_guide_on_2026_09_14_points_at_the_open_round() -> None:
    guide = _guide(date(2026, 9, 14))
    assert [(r["key"], r["label"], r["status"], r["documentsDueBy"]) for r in guide["rounds"]] == [
        ("1", "1차", "current", "2026-09-14"),
        ("2", "2차", "current", "2026-11-18"),
    ]
    assert guide["currentRoundKey"] == "2"
    assert guide["applyFormUrl"] == ROUND2_APPLY_FORM
    assert guide["documentDeadlineDaysAfterTrip"] == 14
    assert guide["minNights"] == 1 and guide["minPaymentKrw"] == 100_000
    assert len(guide["requiredDocuments"]) == 5 and len(guide["exclusions"]) == 9
    assert guide["contacts"]["email"] == "info@visitisland.kr"


def test_guide_after_the_apply_deadline_keeps_the_round_but_closes_the_form() -> None:
    guide = _guide(date(2026, 9, 22))
    assert [(r["key"], r["status"]) for r in guide["rounds"]] == [("1", "past"), ("2", "current")]
    assert guide["currentRoundKey"] == "2"
    assert guide["applyFormUrl"] is None
    assert guide["rounds"][1]["applicationFormUrl"] == ROUND2_APPLY_FORM  # still listed, just not the CTA


def test_guide_after_every_round_has_no_current_round() -> None:
    guide = _guide(date(2026, 11, 19))
    assert [r["status"] for r in guide["rounds"]] == ["past", "past"]
    assert guide["currentRoundKey"] is None
    assert guide["applyFormUrl"] is None


def test_guide_drops_form_links_that_are_not_google_forms() -> None:
    from app.services.island_application_guide import application_guide_for_api
    from app.services.policy_semantic_mapping import map_external_source_semantics

    detail = deepcopy(map_external_source_semantics(island_record()).structured_detail)
    detail["applicationGuide"]["rounds"][1]["applicationFormUrl"] = "https://evil.example/form"
    guide = application_guide_for_api(detail, today=date(2026, 9, 14))
    assert guide["rounds"][1]["applicationFormUrl"] is None
    assert guide["applyFormUrl"] is None


@pytest.mark.parametrize("detail", [None, {}, {"supportContent": []}, {"applicationGuide": "garbage"}])
def test_guide_is_none_without_a_usable_procedure(detail) -> None:
    from app.services.island_application_guide import application_guide_for_api

    assert application_guide_for_api(detail, today=date(2026, 9, 14)) is None


def test_policy_to_api_exposes_the_guide_and_the_open_apply_url(monkeypatch) -> None:
    from app.schemas.policy import Policy as PolicyDTO
    from app.services import policies as policy_service
    from app.services.policy_semantic_mapping import map_external_source_semantics

    monkeypatch.setattr(policy_service, "policy_visibility_date", lambda: date(2026, 9, 14))
    policy = Policy(
        id=310,
        slug="travelmonth-81",
        title="2026 섬 여행비 지원",
        region="전국",
        status="active",
        source_category="island_visit",
        benefit_detail="여행비 10만원",
        official_url="https://www.visitisland.kr/promotion2",
        structured_detail=map_external_source_semantics(island_record()).structured_detail,
    )

    payload = policy_service.policy_to_api(policy)

    assert payload["applicationGuide"]["currentRoundKey"] == "2"
    assert payload["applyUrl"] == ROUND2_APPLY_FORM
    assert payload["structuredDetail"]["requiredDocuments"]
    assert "applicationGuide" not in payload["structuredDetail"]
    dto = PolicyDTO(**payload)
    assert dto.applicationGuide is not None
    assert dto.applicationGuide.rounds[1].applicationFormUrl == ROUND2_APPLY_FORM


def test_policy_to_api_other_policies_have_no_guide(monkeypatch) -> None:
    from app.services import policies as policy_service

    monkeypatch.setattr(policy_service, "policy_visibility_date", lambda: date(2026, 9, 14))
    policy = Policy(id=9, slug="plain", title="Plain", region="강원", status="active", source_category="local_half_trip")
    payload = policy_service.policy_to_api(policy)
    assert payload.get("applicationGuide") is None
    assert payload["applyUrl"] is None


# --- evidence fingerprint -------------------------------------------------------------------------


def test_fingerprint_is_unchanged_for_records_without_a_procedure() -> None:
    from app.services.policy_candidate_review import evidence_fingerprint

    record = island_record(raw_payload={"applicationPeriod": "x"})
    card_copy = card_copy_for_record(record)
    expected_payload = {
        "title": record.title,
        "organizer": record.organizer_text,
        "benefit": record.benefit_text,
        "startDate": record.start_date.isoformat() if record.start_date else None,
        "endDate": record.end_date.isoformat() if record.end_date else None,
        "region": record.region,
        "city": record.city,
        "officialUrl": record.detail_url or record.source_url,
        "status": record.status,
        "benefitValueText": record.benefit_value_text,
        "cardCopy": {"summary": card_copy.summary, "issues": list(card_copy.issues)},
    }
    encoded = json.dumps(expected_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert evidence_fingerprint(record) == hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    without_procedure = island_record(raw_payload={"applicationPeriod": "different"})
    assert evidence_fingerprint(record) == evidence_fingerprint(without_procedure)


def test_fingerprint_changes_when_only_the_procedure_changes() -> None:
    from app.services.policy_candidate_review import evidence_fingerprint

    original = island_record()
    changed_payload = deepcopy(original.raw_payload)
    changed_payload["procedure"]["rounds"][1]["documentFormUrl"] = "https://forms.gle/NewDocumentForm"
    changed = island_record(raw_payload=changed_payload)
    assert evidence_fingerprint(original) != evidence_fingerprint(changed)
