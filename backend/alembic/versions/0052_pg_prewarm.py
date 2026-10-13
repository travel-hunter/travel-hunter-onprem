"""pg_prewarm 확장 - 앱이 뜰 때 장소 검색 표를 미리 읽어 둔다(차가운 첫 검색 7.6초, 10/12 실측)

Revision ID: 0052_pg_prewarm
Revises: 0051_public_place_name_trgm
Create Date: 2026-10-12

- 신뢰 확장이 아니다: 로컬 · 개발 Postgres 컨테이너의 POSTGRES_USER(슈퍼유저)나 AWS RDS 의 마스터 사용자(rds_superuser)가 만든다.
- 데우기(app/services/search_warmup.py)는 'read' 방식이라 shared_buffers 를 차지하지 않고 운영체제 캐시만 채운다. 표 · 색인은 건드리지 않는다.
"""
from collections.abc import Sequence

from alembic import op


revision: str = "0052_pg_prewarm"
down_revision: str | None = "0051_public_place_name_trgm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_prewarm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_prewarm")
