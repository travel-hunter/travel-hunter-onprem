from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


postgres_json = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    preferred_regions: Mapped[str | None] = mapped_column(String(255))
    travel_style: Mapped[str | None] = mapped_column(String(50))
    travel_budget: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user")
    onboarding_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    nickname_setup_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    profile_setup_skipped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    terms_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    terms_version: Mapped[str | None] = mapped_column(String(32))
    privacy_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    privacy_version: Mapped[str | None] = mapped_column(String(32))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime)
    withdrawn_email_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    refresh_tokens: Mapped[list[AuthRefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    social_accounts: Mapped[list[SocialAccount]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    owned_trips: Mapped[list[Trip]] = relationship(back_populates="owner")
    trip_memberships: Mapped[list[TripMember]] = relationship(back_populates="user")
    created_invites: Mapped[list[TripInvite]] = relationship(back_populates="creator")
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="user")
    saved_policies: Mapped[list[UserSavedPolicy]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notification_deliveries: Mapped[list[NotificationDelivery]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    admin_audit_logs: Mapped[list[AdminAuditLog]] = relationship(back_populates="admin_user")


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class PendingSignup(Base):
    __tablename__ = "pending_signups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    terms_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    terms_version: Mapped[str | None] = mapped_column(String(32))
    privacy_accepted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    privacy_version: Mapped[str | None] = mapped_column(String(32))


class PendingSocialSignup(Base):
    __tablename__ = "pending_social_signups"
    __table_args__ = (UniqueConstraint("provider", "provider_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    nickname: Mapped[str | None] = mapped_column(String(100))
    redirect_path: Mapped[str] = mapped_column(String(500), nullable=False, server_default="/home")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("provider", "provider_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_nickname: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="social_accounts")


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str | None] = mapped_column(String(160), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(100))
    policy_type: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    benefit_amount: Mapped[int | None] = mapped_column(Integer)
    benefit_detail: Mapped[str | None] = mapped_column(Text)
    # 카드에만 쓰는 짧은 혜택 문구. 관리자가 승인한 값만 들어간다. benefit_detail 은 상세·일정 금액의
    # 원천이라 카드 때문에 손대지 않는다 - 그래서 필드를 따로 둔다. null 이면 읽기 시점에
    # 깨끗한 amount 를 대신 쓴다(policy_card_quality.public_card_summary_for_policy).
    card_summary: Mapped[str | None] = mapped_column(Text)
    structured_detail: Mapped[dict[str, Any] | None] = mapped_column(postgres_json)
    target_condition: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str | None] = mapped_column(String(80))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    official_url: Mapped[str | None] = mapped_column(String(500))
    apply_url: Mapped[str | None] = mapped_column(String(500))
    policy_comment: Mapped[str | None] = mapped_column(String(300))
    policy_period: Mapped[str | None] = mapped_column(String(100))
    source_type: Mapped[str | None] = mapped_column(String(50), index=True)
    source_name: Mapped[str | None] = mapped_column(String(100), index=True)
    source_category: Mapped[str | None] = mapped_column(String(80), index=True)
    external_source_record_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("external_source_records.id", ondelete="SET NULL"),
        index=True,
    )
    source_url: Mapped[str | None] = mapped_column(String(500))
    source_canonical_key: Mapped[str | None] = mapped_column(String(160), index=True)
    normalized_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    verification_status: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    admin_override_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list[PolicyDocument]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )
    trip_links: Mapped[list[TripPolicy]] = relationship(back_populates="policy")
    user_saves: Mapped[list[UserSavedPolicy]] = relationship(back_populates="policy")
    notification_deliveries: Mapped[list[NotificationDelivery]] = relationship(
        back_populates="policy"
    )


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(String(300))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(postgres_json)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(postgres_json)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    admin_user: Mapped[User] = relationship(back_populates="admin_audit_logs")


class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    document_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    policy: Mapped[Policy] = relationship(back_populates="documents")


class ExternalSourceRecord(Base):
    __tablename__ = "external_source_records"
    __table_args__ = (
        UniqueConstraint("source_name", "source_category", "canonical_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    canonical_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    logical_key: Mapped[str | None] = mapped_column(String(200), index=True)
    canonical_key_version: Mapped[str | None] = mapped_column(String(30))
    detail_url: Mapped[str | None] = mapped_column(String(500))
    collected_page_url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    organizer_text: Mapped[str] = mapped_column(String(300), nullable=False)
    organizers: Mapped[list[str]] = mapped_column(postgres_json, nullable=False)
    region: Mapped[str | None] = mapped_column(String(50), index=True)
    city: Mapped[str | None] = mapped_column(String(80))
    is_nationwide: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    status_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, index=True)
    benefit_text: Mapped[str] = mapped_column(Text, nullable=False)
    benefit_value_text: Mapped[str | None] = mapped_column(String(300))
    extracted_amount_krw: Mapped[int | None] = mapped_column(Integer)
    extracted_discount_percent: Mapped[int | None] = mapped_column(Integer)
    benefit_value_type: Mapped[str] = mapped_column(String(30), nullable=False)
    tags: Mapped[list[str]] = mapped_column(postgres_json, nullable=False)
    contact_text: Mapped[str | None] = mapped_column(String(200))
    inferred_travel_styles: Mapped[list[str]] = mapped_column(postgres_json, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    field_completeness: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_list_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_detail_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(postgres_json, nullable=False)
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    freshness_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PolicyReviewCandidate(Base):
    __tablename__ = "policy_review_candidates"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_policy_review_candidates_review_status",
        ),
        CheckConstraint(
            "change_kind IN ('new', 'material_change')",
            name="ck_policy_review_candidates_change_kind",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    external_source_record_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("external_source_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    change_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(Text)
    # Why the candidate is waiting for a human ('auto' when the gate published it).
    review_reason: Mapped[str | None] = mapped_column(String(40))
    # full_policy: 승인하면 일반 승격(상세까지). card_copy_only: 기존 공개 정책의 카드 문구만 바뀐 후보 -
    # 승인해도 card_summary 만 갱신한다. 둘이 같은 목록에 섞이므로 화면이 구분해 보여 준다.
    review_scope: Mapped[str] = mapped_column(String(24), nullable=False, server_default="full_policy")
    # 카드 문구를 뺀 나머지의 해시. 다음 후보가 '상세는 그대로, 카드 문구만' 바뀐 것인지 여기와 비교한다.
    detail_fingerprint: Mapped[str | None] = mapped_column(String(64))
    published_policy_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("policies.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class PolicyCollectionSource(Base):
    __tablename__ = "policy_collection_sources"
    __table_args__ = (
        CheckConstraint(
            "publication_mode IN ('review', 'auto_after_reviewed_baseline')",
            name="ck_policy_collection_sources_publication_mode",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    adapter_key: Mapped[str] = mapped_column(String(80), nullable=False)
    official_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    publication_mode: Mapped[str] = mapped_column(String(40), nullable=False, server_default="review")
    expected_min_records: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_parsed_count: Mapped[int | None] = mapped_column(Integer)
    last_outcome: Mapped[str | None] = mapped_column(String(40))
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_successful_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class EligibleIslandCatalog(Base):
    __tablename__ = "eligible_island_catalogs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    notice_list_url: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    # ponytail: no FK — snapshots<->catalog would be circular; snapshots are never deleted (status only).
    approved_snapshot_id: Mapped[int | None] = mapped_column(BigInteger().with_variant(Integer, "sqlite"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class EligibleIslandCatalogSnapshot(Base):
    __tablename__ = "eligible_island_catalog_snapshots"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected', 'superseded')",
            name="ck_eligible_island_catalog_snapshots_review_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    catalog_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("eligible_island_catalogs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notice_url: Mapped[str | None] = mapped_column(String(500))
    notice_title: Mapped[str | None] = mapped_column(String(300))
    attachment_url: Mapped[str | None] = mapped_column(String(500))
    attachment_filename: Mapped[str | None] = mapped_column(String(255))
    attachment_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    attachment_documents: Mapped[list[dict[str, Any]]] = mapped_column(postgres_json, nullable=False, default=list)
    parser_version: Mapped[str] = mapped_column(String(40), nullable=False, server_default="v1")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    added_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    removed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    changed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending", default="pending")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class EligibleIslandSnapshotEntry(Base):
    __tablename__ = "eligible_island_snapshot_entries"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "normalized_name", "jurisdiction_name",
            name="uq_eligible_island_snapshot_entries_snapshot_name_jurisdiction",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("eligible_island_catalog_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    jurisdiction_name: Mapped[str] = mapped_column(String(120), nullable=False)
    raw_region_text: Mapped[str | None] = mapped_column(String(300))
    row_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class EligibleIsland(Base):
    __tablename__ = "eligible_islands"
    __table_args__ = (
        UniqueConstraint(
            "catalog_id", "normalized_name", "jurisdiction_name",
            name="uq_eligible_islands_catalog_name_jurisdiction",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    catalog_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("eligible_island_catalogs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("eligible_island_catalog_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    jurisdiction_name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class RegionPhoto(Base):
    __tablename__ = "region_photos"
    __table_args__ = (
        UniqueConstraint("provider", "sido", "city"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    # sido는 policies.region과 동일한 축약형(전남/경북)만 저장한다. 정식명 금지.
    sido: Mapped[str] = mapped_column(String(50), nullable=False)
    # ''는 시도 대표 사진 sentinel. NULL이면 UNIQUE가 중복 삽입을 못 막는다.
    city: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")
    provider_content_id: Mapped[str | None] = mapped_column(String(60))
    content_title: Mapped[str | None] = mapped_column(String(200))
    hero_image_url: Mapped[str | None] = mapped_column(String(500))
    thumb_image_url: Mapped[str | None] = mapped_column(String(500))
    provider_image_url: Mapped[str | None] = mapped_column(String(500))
    storage_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="remote"
    )
    attribution_text: Mapped[str] = mapped_column(
        String(120), nullable=False, server_default="사진: 한국관광공사"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    # 사진 수집 기준(0046): 저작권 유형(cpyrhtDivCd Type1·Type3) · 실제 크기 · 고른 이유. 기준 이전 줄은 비어 있다.
    copyright_type: Mapped[str | None] = mapped_column(String(20))
    image_width: Mapped[int | None] = mapped_column(Integer)
    image_height: Mapped[int | None] = mapped_column(Integer)
    selection_reason: Mapped[str | None] = mapped_column(String(30))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PolicyPhotoAssignment(Base):
    __tablename__ = "policy_photos"
    __table_args__ = (UniqueConstraint("policy_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    policy_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policies.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_content_id: Mapped[str | None] = mapped_column(String(60))
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    alt_text: Mapped[str] = mapped_column(String(200), nullable=False)
    attribution_text: Mapped[str] = mapped_column(String(120), nullable=False)
    relevance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_reason: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="active"
    )
    # 사진 수집 기준(0046): 저작권 유형(cpyrhtDivCd Type1·Type3) · 실제 크기. 기준 이전 줄은 비어 있다.
    copyright_type: Mapped[str | None] = mapped_column(String(20))
    image_width: Mapped[int | None] = mapped_column(Integer)
    image_height: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )



class PhotoReviewTarget(Base):
    """검토할 사진 대상 하나 - 시군(도 전체 포함) 또는 정책. 관리자가 확정한 후보(approved_candidate_id)가 곧 앱 사진이다(0047)."""

    __tablename__ = "photo_review_targets"
    __table_args__ = (
        CheckConstraint("target_type IN ('region', 'policy')", name="ck_photo_review_targets_type"),
        CheckConstraint("status IN ('pending', 'approved', 'none')", name="ck_photo_review_targets_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # region:전남|담양 · region:전남|(도 전체) · policy:123
    target_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sido: Mapped[str] = mapped_column(String(50), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")
    policy_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("policies.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    approved_candidate_id: Mapped[int | None] = mapped_column(BigInteger)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    decided_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    candidates: Mapped[list[PhotoReviewCandidate]] = relationship(
        back_populates="target",
        cascade="all, delete-orphan",
        order_by="PhotoReviewCandidate.id",
    )


class PhotoReviewCandidate(Base):
    """대상마다 후보 사진. source: collect(수집) · search(이름으로 찾기)."""

    __tablename__ = "photo_review_candidates"
    __table_args__ = (
        UniqueConstraint("target_id", "image_url", name="uq_photo_review_candidates_target_image"),
        CheckConstraint("source IN ('collect', 'search')", name="ck_photo_review_candidates_source"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("photo_review_targets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_content_id: Mapped[str | None] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type_id: Mapped[str | None] = mapped_column(String(10))
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    copyright_type: Mapped[str | None] = mapped_column(String(20))
    image_width: Mapped[int | None] = mapped_column(Integer)
    image_height: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str | None] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    search_keyword: Mapped[str | None] = mapped_column(String(100))
    # 확정할 때 받아 둔 원본(MEDIA_ROOT 아래 상대 경로 · 크기 · 형식). 앱은 이 파일만 내보낸다 - 관광공사 주소를 걸지 않는다
    stored_path: Mapped[str | None] = mapped_column(String(300))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    target: Mapped[PhotoReviewTarget] = relationship(back_populates="candidates")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    region: Mapped[str | None] = mapped_column(String(100))
    travel_area_id: Mapped[str | None] = mapped_column(String(120), index=True)
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[User] = relationship(back_populates="owned_trips")
    days: Mapped[list[TripDay]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    members: Mapped[list[TripMember]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    policies: Mapped[list[TripPolicy]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    invites: Mapped[list[TripInvite]] = relationship(
        back_populates="trip", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list[Recommendation]] = relationship(back_populates="trip")


class TripDay(Base):
    __tablename__ = "trip_days"
    __table_args__ = (
        UniqueConstraint("trip_id", "day_number"),
        UniqueConstraint("trip_id", "date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="days")
    places: Mapped[list[TripPlace]] = relationship(
        back_populates="trip_day", cascade="all, delete-orphan"
    )


class TripPlace(Base):
    __tablename__ = "trip_places"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_day_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trip_days.id", ondelete="CASCADE"), nullable=False
    )
    place_name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    source_provider: Mapped[str | None] = mapped_column(String(40))
    external_place_id: Mapped[str | None] = mapped_column(String(80), index=True)
    category_group_code: Mapped[str | None] = mapped_column(String(20))
    category_group_name: Mapped[str | None] = mapped_column(String(80))
    place_url: Mapped[str | None] = mapped_column(String(500))
    visit_time: Mapped[time | None] = mapped_column(Time)
    order_num: Mapped[int | None] = mapped_column(Integer)
    memo: Mapped[str | None] = mapped_column(Text)

    trip_day: Mapped[TripDay] = relationship(back_populates="places")


class TripMember(Base):
    __tablename__ = "trip_members"
    __table_args__ = (UniqueConstraint("trip_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="editor")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    trip: Mapped[Trip] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="trip_memberships")


class TripPolicy(Base):
    __tablename__ = "trip_policies"
    __table_args__ = (
        UniqueConstraint("trip_id", "policy_id"),
        CheckConstraint(
            "application_status IS NULL OR application_status IN "
            "('not_started', 'applied', 'selected', 'not_selected', 'traveled', 'documents_submitted', 'paid')",
            name="ck_trip_policies_application_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False
    )
    policy_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policies.id"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    # Team-level application progress (island support). Checklist stores only which documents are ready — never files.
    application_status: Mapped[str | None] = mapped_column(String(24))
    application_checklist: Mapped[dict[str, Any] | None] = mapped_column(postgres_json)
    application_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    application_updated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )

    trip: Mapped[Trip] = relationship(back_populates="policies")
    policy: Mapped[Policy] = relationship(back_populates="trip_links")


class UserSavedPolicy(Base):
    __tablename__ = "user_saved_policies"
    __table_args__ = (UniqueConstraint("user_id", "policy_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policies.id"), nullable=False, index=True
    )
    saved_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="saved_policies")
    policy: Mapped[Policy] = relationship(back_populates="user_saves")


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "policy_id",
            "channel",
            "lead_day",
            "target_deadline_date",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("policies.id"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    lead_day: Mapped[int] = mapped_column(Integer, nullable=False)
    target_deadline_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="notification_deliveries")
    policy: Mapped[Policy] = relationship(back_populates="notification_deliveries")


class TripInvite(Base):
    __tablename__ = "trip_invites"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invite_token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, server_default="editor")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    trip: Mapped[Trip] = relationship(back_populates="invites")
    creator: Mapped[User] = relationship(back_populates="created_invites")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    trip_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("trips.id"))
    query: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any] | list[dict[str, Any]] | None] = mapped_column(
        postgres_json
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="recommendations")
    trip: Mapped[Trip | None] = relationship(back_populates="recommendations")
