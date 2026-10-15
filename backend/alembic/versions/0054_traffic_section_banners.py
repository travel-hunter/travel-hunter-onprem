"""hide the travel-month section banner policies

Revision ID: 0054_traffic_section_banners
Revises: 0053_free_tour_add_on_merge
Create Date: 2026-10-15

여행가는 달 교통 페이지는 칸(철도 · 항공 · 자동차 · 렌터카)마다 혜택 항목 뒤에 그 칸을 요약하는 배너를 둔다.
배너는 같은 칸 혜택을 다시 적은 홍보 문구라 정책으로 세우지 않는다(2026-10-15 사용자 결정). 파서는 이제
배너를 건너뛴다(SECTION_BANNERS). 이미 공개된 배너 정책 4건은 여기서 한 번 정리한다:

- 배너 정책은 hidden, 원본 기록은 stale - 기록이 공개 조건으로 남으면 다음 수집 승격이 되살린다.
- 배너를 담은 일정 · 저장은 같은 칸 혜택 정책으로 옮긴다(이미 담았으면 하나만 남긴다).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.travelmonth_traffic_parser import traffic_canonical_key


revision: str = "0054_traffic_section_banners"
down_revision: str | None = "0053_free_tour_add_on_merge"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_CATEGORY = "traffic_benefit"
# 배너(핵심 명칭) → 일정 · 저장을 옮길 같은 칸 혜택(핵심 명칭)
BANNER_HOSTS = {
    "자유로운 기차여행": "인구감소지역 자유여행상품 할인",
    "방방곡곡 국내 여행": "네이버 페이 N포인트 지급 (최대 4만 포인트)",
    "모두를 지키는 안전운전": "인구감소지역 자동차 여행 할인",
    "바다가는 달": "연안지역 제약환경(교통) 개선 및 체류 확대를 위한 렌터카 할인",
}

_POLICY_IDS = sa.text(
    "SELECT p.id FROM policies p JOIN external_source_records r ON r.id = p.external_source_record_id "
    "WHERE r.source_category = :category AND r.canonical_key = :key AND p.status <> 'hidden' ORDER BY p.id"
)


def upgrade() -> None:
    bind = op.get_bind()
    for banner, host in BANNER_HOSTS.items():
        banner_key, host_key = traffic_canonical_key(banner), traffic_canonical_key(host)
        found = bind.execute(_POLICY_IDS, {"category": SOURCE_CATEGORY, "key": banner_key})
        if found is None:  # --sql(오프라인)은 읽을 행이 없다 - 데이터 정리는 실제 DB 에서만
            return
        banner_ids = [row[0] for row in found]
        host_ids = [row[0] for row in bind.execute(_POLICY_IDS, {"category": SOURCE_CATEGORY, "key": host_key})]
        for banner_id in banner_ids:
            ids = {"host": host_ids[0] if host_ids else None, "banner": banner_id}
            for table, owner in (("trip_policies", "trip_id"), ("user_saved_policies", "user_id")):
                if ids["host"] is not None:
                    bind.execute(
                        sa.text(
                            f"UPDATE {table} SET policy_id = :host WHERE policy_id = :banner "
                            f"AND {owner} NOT IN (SELECT {owner} FROM {table} WHERE policy_id = :host)"
                        ),
                        ids,
                    )
                    bind.execute(sa.text(f"DELETE FROM {table} WHERE policy_id = :banner"), ids)
            bind.execute(sa.text("UPDATE policies SET status = 'hidden' WHERE id = :banner"), ids)
        bind.execute(
            sa.text(
                "UPDATE external_source_records SET freshness_status = 'stale' "
                "WHERE source_category = :category AND canonical_key = :key"
            ),
            {"category": SOURCE_CATEGORY, "key": banner_key},
        )


def downgrade() -> None:
    # 정책 · 기록 상태만 되돌린다. 옮긴 일정 · 저장 링크는 그대로 둔다.
    bind = op.get_bind()
    for banner in BANNER_HOSTS:
        params = {"category": SOURCE_CATEGORY, "key": traffic_canonical_key(banner)}
        bind.execute(
            sa.text(
                "UPDATE external_source_records SET freshness_status = 'unknown' "
                "WHERE source_category = :category AND canonical_key = :key"
            ),
            params,
        )
        bind.execute(
            sa.text(
                "UPDATE policies SET status = 'active' WHERE id IN ("
                "  SELECT p.id FROM policies p JOIN external_source_records r ON r.id = p.external_source_record_id"
                "  WHERE r.source_category = :category AND r.canonical_key = :key)"
            ),
            params,
        )
