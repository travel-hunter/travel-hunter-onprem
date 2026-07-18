from app.data import seed
from app.db.seed import seed_policies
from app.db.base import Base
from app.api.routes import policies as policy_routes
from app.main import app
from app.models import Policy, PolicyDocument, PolicySlugAlias, User, UserSavedPolicy
from fastapi.testclient import TestClient
import pytest
from scripts.crawl_dgtourcard import DEFAULT_EXISTING_SLUGS
from scripts.audit_policy_sources import audit_policies, audit_policy
from sqlalchemy import BigInteger, Integer, create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def sqlite_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


def test_seed_policies_migrates_legacy_dgtour_slug_to_canonical_id(
    sqlite_db_session,
) -> None:
    user = User(email="saved@example.com", nickname="saved-user")
    legacy_policy = Policy(
        slug="dgtour-영광-8",
        title="legacy dgtour",
        organization="demo",
        policy_type="digital_tourism_card",
        description="old",
        benefit_detail="old",
        target_condition="old",
        region="전남",
        official_url="https://korean.visitkorea.or.kr/dgtourcard/tour50.do",
    )
    sqlite_db_session.add_all([user, legacy_policy])
    sqlite_db_session.flush()
    legacy_id = legacy_policy.id
    sqlite_db_session.add(UserSavedPolicy(user_id=user.id, policy_id=legacy_id))
    sqlite_db_session.commit()

    seed_policies(sqlite_db_session)
    sqlite_db_session.commit()

    canonical_policy = sqlite_db_session.scalar(
        select(Policy).where(Policy.slug == "dgtour-yeonggwang-8")
    )
    legacy_policy = sqlite_db_session.scalar(
        select(Policy).where(Policy.slug == "dgtour-영광-8")
    )
    alias = sqlite_db_session.scalar(
        select(PolicySlugAlias).where(PolicySlugAlias.old_slug == "dgtour-영광-8")
    )
    saved_policy = sqlite_db_session.scalar(select(UserSavedPolicy))

    assert canonical_policy is not None
    assert canonical_policy.id == legacy_id
    assert legacy_policy is None
    assert saved_policy is not None
    assert saved_policy.policy_id == canonical_policy.id
    assert alias is not None
    assert alias.policy_id == canonical_policy.id
    assert alias.canonical_slug == "dgtour-yeonggwang-8"
    assert alias.alias_kind == "legacy"
    assert alias.source_kind == "seed"
    assert alias.is_active is True
    assert alias.superseded_at is None


def test_seeded_legacy_dgtour_detail_redirects_to_canonical_slug(
    sqlite_db_session,
) -> None:
    seed_policies(sqlite_db_session)
    sqlite_db_session.commit()

    app.dependency_overrides[policy_routes.get_optional_db] = lambda: sqlite_db_session
    try:
        response = TestClient(app).get(
            "/api/policies/dgtour-영광-8",
            follow_redirects=False,
        )
    finally:
        app.dependency_overrides.pop(policy_routes.get_optional_db, None)

    assert response.status_code == 307
    assert response.headers["location"] == "/api/policies/dgtour-yeonggwang-8"
