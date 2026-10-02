"""photo review: collection writes candidates, an admin approves one per target

Revision ID: 0047_photo_review
Revises: 0046_photo_criteria
Create Date: 2026-10-02

수집은 시군 · 정책마다 사진 후보만 넣고, 관리자가 한 장을 확정해야 앱에 나간다(2026-10-01 사용자 결정,
docs/superpowers/plans/2026-10-02-photo-review-stage.md). 앱은 '대상이 고른 후보'를 바로 읽는다(표 2개, 10/2 결정).
확정할 때 원본을 MEDIA_ROOT 에 받아 두고(stored_path) 그 파일만 /api/media 로 내보낸다 - 관광공사 주소를 걸지 않는다.
region_photos · policy_photos 는 더 읽지도 쓰지도 않는다. 아래에서 review 로 내린 채 남겨 두고, 배포가 확인되면 따로 지운다.

데이터: 기존 active 사진 줄을 review 로 내린다(검토 전으로 돌림 - 화면은 혜택 그림). 후보로 옮기지는 않는다 - 수집 기준
(0046) 이전에 고른 사진이라 저작권 유형을 몰라 확정할 수 없다. 대상과 후보는 수집(scripts/collect_photo_candidates.py)이
만든다. downgrade 는 review → active 로 되돌리고 새 표를 지운다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0047_photo_review"
down_revision: str | None = "0046_photo_criteria"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo_review_targets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("target_key", sa.String(length=160), nullable=False, unique=True),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("sido", sa.String(length=50), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("policy_id", sa.BigInteger(), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("approved_candidate_id", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decided_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("target_type IN ('region', 'policy')", name="ck_photo_review_targets_type"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'none')", name="ck_photo_review_targets_status"),
    )
    op.create_index("ix_photo_review_targets_type_status", "photo_review_targets", ["target_type", "status"])
    op.create_table(
        "photo_review_candidates",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "target_id", sa.BigInteger(), sa.ForeignKey("photo_review_targets.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_content_id", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_type_id", sa.String(length=10), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_url", sa.String(length=500), nullable=True),
        sa.Column("copyright_type", sa.String(length=20), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("address", sa.String(length=200), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("search_keyword", sa.String(length=100), nullable=True),
        sa.Column("stored_path", sa.String(length=300), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("target_id", "image_url", name="uq_photo_review_candidates_target_image"),
        sa.CheckConstraint("source IN ('collect', 'search')", name="ck_photo_review_candidates_source"),
    )
    op.create_index("ix_photo_review_candidates_target_id", "photo_review_candidates", ["target_id"])

    # 기존 자동 사진은 화면에서만 내린다(검토 전으로 돌림)
    op.execute("UPDATE region_photos SET status = 'review' WHERE status = 'active'")
    op.execute("UPDATE policy_photos SET status = 'review' WHERE status = 'active'")


def downgrade() -> None:
    op.execute("UPDATE policy_photos SET status = 'active' WHERE status = 'review'")
    op.execute("UPDATE region_photos SET status = 'active' WHERE status = 'review'")
    op.drop_index("ix_photo_review_candidates_target_id", table_name="photo_review_candidates")
    op.drop_table("photo_review_candidates")
    op.drop_index("ix_photo_review_targets_type_status", table_name="photo_review_targets")
    op.drop_table("photo_review_targets")
