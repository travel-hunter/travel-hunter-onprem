"""trip place public category + user label + public places area index (Kakao Local policy, stage 3)

Revision ID: 0049_trip_place_public_category
Revises: 0048_public_places
Create Date: 2026-10-05

3단계 담는 흐름(설계 docs/superpowers/specs/2026-10-03-public-place-storage-design.md)이 쓴다.
- trip_places.public_category: 공공데이터 장소를 담을 때 그 분류(public_places.category)를 복사한다. 일정 화면이 시간대와
  분류 표시에 쓴다. nullable - 나만의 장소와 예전 행은 비어 있다. 값은 public_places 와 같은 7개로 CHECK 한다.
- trip_places.user_label: 사용자가 붙인 이름. 공공데이터 장소(place_origin='public')의 이름을 고쳐도 place_name(공공데이터 이름)은
  그대로 두고 여기에 담는다. 화면 이름은 user_label 이 있으면 그것, 없으면 place_name. nullable - 나만의 장소와 예전 행은 비어 있다.
- ix_public_places_sido_city: 추천 · 지역 중심 조회가 일정 지역(시도 + 시군)으로 거른다. public_places 는 108만 행이라 CONCURRENTLY 로
  만들어 TourAPI 동기화 · 상가정보 적재(쓰기)를 막지 않는다.
열 둘과 색인만 더하므로 앞 버전 코드가 그대로 돈다. downgrade 는 셋 다 지운다.

CONCURRENTLY 는 트랜잭션 안에서 못 돌려서 autocommit_block 으로 감싼다(블록 앞까지 커밋된다). 그래서 색인을 맨 앞에 둔다 - 이 단계가
실패해도 열 · 제약 · 버전 표는 그대로이고 남는 것은 INVALID 색인 하나뿐이다. 블록은 만들기 전에 같은 이름의 색인을 지우므로
(DROP INDEX CONCURRENTLY IF EXISTS) 배포를 다시 돌리면 스스로 풀린다. 이 블록은 0049 가 버전 표에 오르기 전에만 돌아서 지우는 것은
앞선 시도가 남긴 색인뿐이다. IF NOT EXISTS 로 만들지 않는다 - INVALID 색인을 그대로 두고 지나간다.
열 · 제약은 그 뒤 한 트랜잭션이라 버전 표 갱신과 함께 되돌려진다.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0049_trip_place_public_category"
down_revision: str | None = "0048_public_places"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        # 앞선 시도가 실패해 남긴 INVALID 색인 - 지워야 다시 돌리기가 풀린다(0049 가 오르기 전에만 도는 자리다)
        op.drop_index("ix_public_places_sido_city", table_name="public_places", postgresql_concurrently=True, if_exists=True)
        op.create_index("ix_public_places_sido_city", "public_places", ["sido", "city"], postgresql_concurrently=True)
    op.add_column("trip_places", sa.Column("public_category", sa.String(length=20), nullable=True))
    op.add_column("trip_places", sa.Column("user_label", sa.String(length=100), nullable=True))
    op.create_check_constraint(
        "ck_trip_places_public_category",
        "trip_places",
        "public_category IS NULL OR public_category IN ('sight', 'culture', 'leisure', 'stay', 'shopping', 'food', 'cafe')",
    )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index("ix_public_places_sido_city", table_name="public_places", postgresql_concurrently=True, if_exists=True)
    op.drop_constraint("ck_trip_places_public_category", "trip_places", type_="check")
    op.drop_column("trip_places", "user_label")
    op.drop_column("trip_places", "public_category")
