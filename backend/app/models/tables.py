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
    structured_detail: Mapped[dict[str, Any] | None] = mapped_column(postgres_json)
    target_condition: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
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
        unique=True,
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
    status_text: Mapped[str | None] = mapped_column(String(50))
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
    __table_args__ = (UniqueConstraint("trip_id", "policy_id"),)

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
