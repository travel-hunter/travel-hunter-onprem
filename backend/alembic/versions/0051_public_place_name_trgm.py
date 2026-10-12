"""public_places 이름 trigram 색인 - 장소 검색 완성 검색어(ILIKE '%q%')

Revision ID: 0051_public_place_name_trgm
Revises: 0050_geo_reference
Create Date: 2026-10-12

- pg_trgm 은 신뢰 확장(PG13+) - DB 소유자가 만들 수 있다. AWS RDS 도 지원한다.
- 108만 행에서 약 78MB(81,805,312 B), 만드는 데 약 7초(2026-10-12 실측). CONCURRENTLY 라 적재 · 동기화 쓰기를 막지 않는다(0049 관례).
"""
from collections.abc import Sequence

from alembic import op


revision: str = "0051_public_place_name_trgm"
down_revision: str | None = "0050_geo_reference"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    with op.get_context().autocommit_block():
        # 앞선 시도가 실패해 남긴 INVALID 색인 - 지워야 다시 돌리기가 풀린다
        op.drop_index("ix_public_places_name_trgm", table_name="public_places", postgresql_concurrently=True, if_exists=True)
        op.create_index(
            "ix_public_places_name_trgm", "public_places", ["name"],
            postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}, postgresql_concurrently=True,
        )


def downgrade() -> None:
    # 확장은 남긴다 - 다른 객체가 쓸 수 있다
    with op.get_context().autocommit_block():
        op.drop_index("ix_public_places_name_trgm", table_name="public_places", postgresql_concurrently=True, if_exists=True)
