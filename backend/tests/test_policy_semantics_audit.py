import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Policy
from scripts import audit_policy_semantics as script


class NonClosingSessionFactory:
    def __init__(self, db: Session) -> None:
        self.db = db

    def __call__(self) -> "NonClosingSessionFactory":
        return self

    def __enter__(self) -> Session:
        return self.db

    def __exit__(self, *_args: object) -> None:
        return None


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with TestingSessionLocal() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)


def add_policy(db: Session, **overrides: object) -> Policy:
    payload = {
        "id": overrides.pop("id"),
        "slug": overrides.pop("slug"),
        "title": "Aggregate audit fixture",
        "region": "전국",
        "status": "active",
    }
    payload.update(overrides)
    policy = Policy(**payload)
    db.add(policy)
    return policy


def seed_policies(db: Session) -> None:
    add_policy(
        db,
        id=1,
        slug="active-legacy",
        status="active",
        benefit_amount=10000,
        apply_url="https://apply.example/legacy",
        source_type="official",
        source_name="디지털관광주민증",
        source_category="regional_discount",
        source_canonical_key="legacy-dgtour-밀양-1",
    )
    add_policy(
        db,
        id=2,
        slug="hidden-hex",
        status="hidden",
        benefit_amount=None,
        apply_url=None,
        source_type="official",
        source_name="여행가는 달",
        source_category="regional_benefit",
        source_canonical_key="0123456789abcdef0123456789abcdef",
    )
    add_policy(
        db,
        id=3,
        slug="active-travelmonth",
        status="active",
        benefit_amount=50000,
        apply_url=None,
        source_type="official",
        source_name="여행가는 달",
        source_category="regional_benefit",
        source_canonical_key="travelmonth-101",
    )
    add_policy(
        db,
        id=4,
        slug="active-null-source",
        status="active",
        benefit_amount=None,
        apply_url="https://apply.example/null-source",
        source_type=None,
        source_name=None,
        source_category=None,
        source_canonical_key=None,
    )
    add_policy(
        db,
        id=5,
        slug="hidden-other",
        status="hidden",
        benefit_amount=None,
        apply_url=None,
        source_type="partner",
        source_name="other-source",
        source_category="other-category",
        source_canonical_key="unprefixed-key",
    )
    db.commit()


def test_canonical_key_family_groups_expected_formats() -> None:
    assert script.canonical_key_family(None) == "null"
    assert script.canonical_key_family("   ") == "null"
    assert script.canonical_key_family("legacy-dgtour-하동-3") == "legacy-dgtour"
    assert script.canonical_key_family("0123456789abcdef0123456789ABCDEF") == "32-char-hex"
    assert script.canonical_key_family("travelmonth-101") == "travelmonth/source-prefixed"
    assert script.canonical_key_family("external:abc") == "travelmonth/source-prefixed"
    assert script.canonical_key_family("plain-key") == "other"


def test_audit_policy_semantics_returns_aggregate_counts_without_raw_rows(db: Session) -> None:
    seed_policies(db)

    payload = script.audit_policy_semantics(db)

    assert payload == {
        "totalPolicies": 5,
        "statusCounts": {"active": 3, "hidden": 2},
        "benefitAmount": {"null": 3, "nonNull": 2},
        "applyUrl": {"null": 3, "nonNull": 2},
        "sourceCombinations": {
            "distinctCount": 4,
            "items": [
                {
                    "sourceType": "official",
                    "sourceName": "여행가는 달",
                    "sourceCategory": "regional_benefit",
                    "count": 2,
                },
                {
                    "sourceType": None,
                    "sourceName": None,
                    "sourceCategory": None,
                    "count": 1,
                },
                {
                    "sourceType": "official",
                    "sourceName": "디지털관광주민증",
                    "sourceCategory": "regional_discount",
                    "count": 1,
                },
                {
                    "sourceType": "partner",
                    "sourceName": "other-source",
                    "sourceCategory": "other-category",
                    "count": 1,
                },
            ],
        },
        "sourceCanonicalKeyFamilies": {
            "legacy-dgtour": 1,
            "32-char-hex": 1,
            "travelmonth/source-prefixed": 1,
            "null": 1,
            "other": 1,
        },
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "active-legacy" not in serialized
    assert "https://apply.example" not in serialized
    assert "legacy-dgtour-밀양-1" not in serialized


def test_main_json_prints_json_object_and_rolls_back_without_mutation(
    db: Session, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seed_policies(db)
    monkeypatch.setattr(script, "get_session_factory", lambda: NonClosingSessionFactory(db))

    exit_code = script.main(["--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totalPolicies"] == 5
    assert payload["statusCounts"] == {"active": 3, "hidden": 2}
    assert db.query(Policy).count() == 5
    assert not db.dirty
    assert not db.new
