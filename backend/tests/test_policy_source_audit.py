from app.data import seed
from app.db.seed import seed_policies
from app.db.base import Base
from app.models import Policy, PolicyDocument
import pytest
from scripts.crawl_dgtourcard import DEFAULT_EXISTING_SLUGS
from scripts.audit_policy_sources import audit_policies, audit_policy
from sqlalchemy import BigInteger, Integer, create_engine, select
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def sqlite_db_session():
    engine = create_engine("sqlite:///:memory:")
    mutated_columns = []
    for table in Base.metadata.tables.values():
        for column in table.c:
            if column.primary_key and isinstance(column.type, BigInteger):
                mutated_columns.append((column, column.type))
                column.type = Integer()

    try:
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
        with TestingSessionLocal() as session:
            yield session
        Base.metadata.drop_all(engine)
    finally:
        for column, original_type in mutated_columns:
            column.type = original_type


def policy(**overrides):
    payload = {
        "slug": "sokcho-stay",
        "title": "속초 워케이션 숙박 지원",
        "org": "속초시",
        "region": "강원",
        "summary": "속초시 워케이션 참여자가 지정 숙소와 체험콘텐츠를 이용할 수 있도록 지원합니다.",
        "amount": "숙박비 및 관광콘텐츠 체험비 지원",
        "category": "숙박",
        "officialUrl": "https://www.sokcho.go.kr/sc/portal/sokchonews/pressrelease?articleSeq=806017",
        "applyUrl": None,
    }
    payload.update(overrides)
    return payload


def test_audit_policy_rejects_portal_root_source() -> None:
    result = audit_policy(policy(officialUrl="https://www.sokcho.go.kr/sc/portal"))

    assert result.status == "invalid_source"
    assert "root" in result.reasons[0]


def test_audit_policy_marks_missing_source() -> None:
    result = audit_policy(policy(officialUrl=None, applyUrl=None))

    assert result.status == "missing_source"


def test_audit_policy_verifies_source_text_alignment() -> None:
    result = audit_policy(
        policy(),
        source_text="2025년 속초 워케이션은 지정 숙소와 관광콘텐츠 체험비를 지원한다.",
    )

    assert result.status == "verified"
    assert result.score >= 35


def test_audit_policy_flags_weak_text_alignment() -> None:
    result = audit_policy(policy(), source_text="속초시 공지사항과 일반 민원 안내입니다.")

    assert result.status == "needs_review"


def test_audit_policies_returns_slug_indexed_results() -> None:
    results = audit_policies([policy(), policy(slug="bad", officialUrl="https://example.com/policy")])

    assert [result.slug for result in results] == ["sokcho-stay", "bad"]
    assert results[1].status == "invalid_source"


def test_seed_policy_data_excludes_legacy_dummy_policy_slugs() -> None:
    slugs = {item["slug"] for item in seed.POLICIES}

    assert {"local-vacation", "sokcho-stay", "busan-cashback"}.isdisjoint(slugs)
    assert slugs


def test_dgtour_crawler_no_longer_reserves_legacy_dummy_slugs() -> None:
    assert {"local-vacation", "sokcho-stay", "busan-cashback"}.isdisjoint(DEFAULT_EXISTING_SLUGS)


def test_seed_policies_deletes_legacy_dummy_policies_from_existing_db(sqlite_db_session) -> None:
    for slug in ("local-vacation", "sokcho-stay", "busan-cashback"):
        existing = Policy(
            slug=slug,
            title=f"legacy {slug}",
            organization="demo",
            policy_type="demo",
            description="old",
            benefit_detail="old",
            target_condition="old",
            region="demo",
            official_url="https://example.org/demo",
        )
        existing.documents = [PolicyDocument(document_name="legacy document")]
        sqlite_db_session.add(existing)
    sqlite_db_session.commit()

    seed_policies(sqlite_db_session)
    sqlite_db_session.commit()

    remaining = sqlite_db_session.scalars(
        select(Policy.slug).where(Policy.slug.in_(["local-vacation", "sokcho-stay", "busan-cashback"]))
    ).all()
    assert remaining == []
