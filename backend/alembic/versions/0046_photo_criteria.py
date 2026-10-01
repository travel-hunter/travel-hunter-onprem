"""record photo collection criteria on region_photos and policy_photos

Revision ID: 0046_photo_criteria
Revises: 0045_traffic_detail
Create Date: 2026-10-01

사진 수집이 홈 배너 사진과 같은 기준(app/services/photo_criteria.py)을 거치게 되면서, 고른 사진의 저작권 유형
(TourAPI cpyrhtDivCd: Type1 공공누리 제1유형 · Type3 제3유형 변경금지)과 실제 크기를 남긴다. 나중에 사진을 자체
보관할 때 제3유형은 다시 인코딩하면 안 되므로 유형이 꼭 필요하다. region_photos 에는 고른 이유도 남긴다
(policy_photos 는 assignment_reason 이 이미 있다).

모두 비워 둘 수 있는 칸이다 - 기준 이전에 넣은 줄은 비어 있고, 수집 스크립트가 그 줄을 다시 고른다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0046_photo_criteria"
down_revision: str | None = "0045_traffic_detail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("region_photos", "policy_photos"):
        op.add_column(table, sa.Column("copyright_type", sa.String(length=20), nullable=True))
        op.add_column(table, sa.Column("image_width", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("image_height", sa.Integer(), nullable=True))
    op.add_column("region_photos", sa.Column("selection_reason", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("region_photos", "selection_reason")
    for table in ("policy_photos", "region_photos"):
        op.drop_column(table, "image_height")
        op.drop_column(table, "image_width")
        op.drop_column(table, "copyright_type")
