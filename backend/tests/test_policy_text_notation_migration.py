"""0055: 저장된 정책 상세의 표기 오류를 고친다(2026-10-15 사용자 결정 - 문체는 그대로, 표기만)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import ExternalSourceRecord, Policy
from app.services import digital_tourism_resident_card as dgtour
from app.services import stay_discount_aliases
from app.services.travelmonth_traffic_detail import TRAFFIC_DETAIL_BY_TITLE

MIGRATION = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0055_policy_text_notation.py"
CUT_TYPE = "여행유형(가족·개인·단체·청년) 중복신청 및 승인 후 유형변경 불가"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0055", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _run_upgrade(db: Session) -> None:
    module = _migration()
    module.op = SimpleNamespace(get_bind=lambda: db.connection())
    module.upgrade()
    db.commit()
    db.expire_all()


def _dgtour_policy(policy_id: int, *, admin_override: bool = False) -> Policy:
    return Policy(
        id=policy_id,
        slug=f"dgtour-{policy_id}",
        title="[하동] 디지털관광주민증",
        region="경남",
        status="active",
        source_category="digital_tourism_resident_card",
        admin_override_enabled=admin_override,
        target_condition="하동 디지털관광주민증을 발급한 여행자",
        structured_detail={
            "applicationTarget": [
                {"title": "신청대상", "description": "하동 디지털관광주민증을 발급한 여행자"},
                {
                    "title": "이용조건",
                    "description": "VisitKorea/대한민국 구석구석에서 디지털관광주민증을 발급하고 제휴처에서 제시해야 합니다.",
                },
            ],
            "notes": [{"title": "비고", "description": "지역별 제휴처와 혜택은 변동될 수 있습니다."}],
        },
    )


def _half_trip_record_and_policy() -> list[object]:
    from tests.test_policy_candidate_review import make_record

    record = make_record()
    record.id = 95
    record.city = "산청"
    record.title = "[산청] 반값여행"
    record.raw_payload = {"notes": f"여행경비 최소 10만 원 이상 결제, {CUT_TYPE}"}
    policy = Policy(
        id=195,
        slug="travelmonth-95",
        title="[산청] 반값여행",
        region="경남",
        status="active",
        source_category="local_half_trip",
        external_source_record_id=95,
        structured_detail={
            "supportContent": [
                {"title": "혜택 적용 조건", "description": "여행유형(가족"},
                {"title": "혜택 적용 조건", "description": "청년) 중복신청 및 승인 후 유형변경 불가"},
            ],
            # 지금 매퍼가 다시 만들지 못하는 저장값 - 잘린 칸이 아니면 그대로 남아야 한다
            "periods": [{"title": "여행 기간", "description": "여행 기간: 9.3~9.30"}],
        },
    )
    return [record, policy]


def _descriptions(detail: dict, section: str) -> list[str]:
    return [item["description"] for item in detail.get(section, [])]


def test_wrong_notation_in_stored_detail_and_target_is_fixed_and_admin_override_is_left_alone() -> None:
    db = _make_session()
    try:
        db.add_all([_dgtour_policy(1), _dgtour_policy(2, admin_override=True)])
        db.commit()

        _run_upgrade(db)

        fixed = db.get(Policy, 1)
        assert fixed.target_condition == "하동 디지털관광주민증을 발급받은 여행자"
        assert _descriptions(fixed.structured_detail, "applicationTarget") == [
            "하동 디지털관광주민증을 발급받은 여행자",
            "VisitKorea(대한민국 구석구석)에서 디지털관광주민증을 발급받고 제휴처에서 제시해야 합니다.",
        ]
        assert _descriptions(fixed.structured_detail, "notes") == ["지역별 제휴처와 혜택은 변동될 수 있습니다."]
        assert db.get(Policy, 2).target_condition == "하동 디지털관광주민증을 발급한 여행자"
    finally:
        db.close()


def test_half_trip_detail_cut_inside_parentheses_is_rebuilt_from_its_record() -> None:
    db = _make_session()
    try:
        db.add_all(_half_trip_record_and_policy())
        db.commit()

        _run_upgrade(db)

        detail = db.get(Policy, 195).structured_detail
        benefits = _descriptions(detail, "supportContent")
        assert CUT_TYPE in benefits
        assert "여행유형(가족" not in benefits
        assert _descriptions(detail, "periods") == ["여행 기간: 9.3~9.30"]
        assert db.get(ExternalSourceRecord, 95).raw_payload["notes"].endswith(CUT_TYPE)  # 기록은 그대로
    finally:
        db.close()


def test_upgrade_twice_gives_the_same_rows() -> None:
    db = _make_session()
    try:
        db.add_all([_dgtour_policy(1), *_half_trip_record_and_policy()])
        db.commit()
        _run_upgrade(db)
        first = {policy.id: (policy.target_condition, policy.structured_detail) for policy in db.query(Policy)}
        _run_upgrade(db)
        assert {policy.id: (policy.target_condition, policy.structured_detail) for policy in db.query(Policy)} == first
    finally:
        db.close()


def test_runtime_mappers_already_write_the_fixed_notation() -> None:
    """마이그레이션 결과와 다음 승격 결과가 같아야 한다 - 지금 코드가 만드는 글자에는 고칠 것이 없다."""
    fix = _migration().fix_notation
    texts = [
        dgtour.USAGE_CONDITION_TEXT,
        dgtour.application_target_text("하동"),
        dgtour.application_target_text(None),
        *(str(item) for detail in TRAFFIC_DETAIL_BY_TITLE.values() for section in detail.values() for item in section),
    ]
    stay_targets = stay_discount_aliases._alias_application_targets(
        stay_discount_aliases.StayDiscountAliasArea(sido="경남", city="고성군", slug="stay-discount-gyeongnam-goseong")
    )
    texts += [str(item) for item in stay_targets]
    for text in texts:
        assert fix(text) == text, text


def test_no_service_source_still_writes_a_wrong_notation() -> None:
    services = Path(__file__).resolve().parents[1] / "app" / "services"
    sources = "".join((services / name).read_text(encoding="utf-8") for name in (
        "digital_tourism_resident_card.py", "policy_semantic_mapping.py",
        "stay_discount_aliases.py", "travelmonth_traffic_detail.py",
    ))
    for wrong, right in _migration().NOTATION_FIXES:
        assert wrong not in sources, wrong


def _half_trip_policy(policy_id: int, record_id: int | None, detail: dict, **fields: object) -> Policy:
    return Policy(
        id=policy_id,
        slug=f"travelmonth-{policy_id}",
        title="[횡성] 반값여행",
        region="강원",
        status="active",
        source_category="local_half_trip",
        external_source_record_id=record_id,
        structured_detail=detail,
        **fields,
    )


def test_reversed_fragment_is_detected_and_the_joined_sentence_lands_in_its_own_section() -> None:
    from tests.test_policy_candidate_review import make_record

    record = make_record()
    record.id = 30
    record.city = "횡성"
    record.raw_payload = {"notes": "참여유형(개인, 단체 동일) 확인 필요 (연 30억원 초과 매출업소 제외)"}
    cut = {"notes": [{"title": "비고", "description": "단체 동일) 확인 필요 (연 30억원 초과 매출업소 제외"}]}
    db = _make_session()
    try:
        assert _migration().has_cut_parentheses(cut)  # 개수는 1:1 이지만 닫는 괄호가 먼저
        db.add_all([record, _half_trip_policy(130, 30, cut)])
        db.commit()

        _run_upgrade(db)

        notes = _descriptions(db.get(Policy, 130).structured_detail, "notes")
        assert "참여유형(개인, 단체 동일) 확인 필요 (연 30억원 초과 매출업소 제외)" in notes
        assert cut["notes"][0]["description"] not in notes
    finally:
        db.close()


def test_half_trip_rows_without_a_record_or_with_admin_override_keep_their_fragments() -> None:
    from tests.test_policy_candidate_review import make_record

    record = make_record()
    record.id = 95
    record.raw_payload = {"notes": CUT_TYPE}
    cut = {"supportContent": [{"title": "혜택 적용 조건", "description": "여행유형(가족"}]}
    db = _make_session()
    try:
        db.add_all([
            record,
            _half_trip_policy(301, None, cut),
            _half_trip_policy(302, 999, cut),  # 가리키는 기록이 없다
            _half_trip_policy(303, 95, cut, admin_override_enabled=True),
        ])
        db.commit()

        _run_upgrade(db)

        for policy_id in (301, 302, 303):
            assert db.get(Policy, policy_id).structured_detail == cut
    finally:
        db.close()


def test_a_cut_target_condition_is_rebuilt_and_a_whole_one_is_kept() -> None:
    db = _make_session()
    try:
        record, policy = _half_trip_record_and_policy()
        policy.target_condition = "여행유형(가족"
        other_record, other = _half_trip_record_and_policy()
        other_record.id, other.id, other.slug, other.external_source_record_id = 96, 196, "travelmonth-96", 96
        other_record.external_id = other_record.canonical_key = "example-2"
        other.target_condition = "사람이 적은 대상"
        db.add_all([record, policy, other_record, other])
        db.commit()

        _run_upgrade(db)

        rebuilt = db.get(Policy, 195).target_condition
        assert rebuilt != "여행유형(가족"
        assert not _migration().has_cut_parentheses(rebuilt)
        assert db.get(Policy, 196).target_condition == "사람이 적은 대상"
    finally:
        db.close()
