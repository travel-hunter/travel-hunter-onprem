"""fold the free-tour add-on traffic policy into the free-tour discount policy

Revision ID: 0053_free_tour_add_on_merge
Revises: 0052_pg_prewarm
Create Date: 2026-10-15

'인구감소지역 자유여행상품 추가 혜택'(13개 지역 온누리상품권)은 같은 코레일 자유여행상품을 사야 받는
덧붙임 혜택이라 '할인' 정책 한 장에 합친다(2026-10-15 사용자 결정). 파서는 이제 추가 혜택 카드를 따로
만들지 않는다(_fold_add_on_records). 이미 공개된 행은 여기서 한 번 정리한다:

- 추가 혜택 정책은 hidden, 원본 기록은 stale - 기록이 공개 조건(fresh)으로 남으면 다음 수집 승격이 되살린다.
- 그 정책을 담은 일정 · 저장은 할인 정책으로 옮긴다(이미 둘 다 담았으면 하나만 남긴다).
- 할인 정책의 상세(structured_detail)와 카드 문구를 합친 내용으로 채운다(0045 와 같은 방식).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

from app.models.tables import postgres_json
from app.services.travelmonth_traffic_detail import structured_detail_for_traffic
from app.services.travelmonth_traffic_parser import traffic_canonical_key


revision: str = "0053_free_tour_add_on_merge"
down_revision: str | None = "0052_pg_prewarm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_CATEGORY = "traffic_benefit"
HOST_KEY = traffic_canonical_key("인구감소지역 자유여행상품 할인")
ADD_ON_KEY = traffic_canonical_key("인구감소지역 자유여행상품 추가 혜택")
HOST_CARD = "방문 인증 운임 쿠폰·온누리 2만원"

_SELECT = sa.text(
    "SELECT p.id AS policy_id, r.title, r.benefit_text, r.raw_payload, r.source_category, "
    "       r.start_date, r.end_date, r.last_fetched_at "
    "FROM policies p JOIN external_source_records r ON r.id = p.external_source_record_id "
    "WHERE r.source_category = :category AND r.canonical_key = :key AND p.status <> 'hidden' "
    "ORDER BY p.id"
)


def upgrade() -> None:
    bind = op.get_bind()
    found = bind.execute(_SELECT, {"category": SOURCE_CATEGORY, "key": HOST_KEY})
    if found is None:  # --sql(오프라인)은 읽을 행이 없다 - 데이터 정리는 실제 DB 에서만
        return
    hosts = found.mappings().all()
    add_ons = bind.execute(_SELECT, {"category": SOURCE_CATEGORY, "key": ADD_ON_KEY}).mappings().all()
    if not hosts or not add_ons:
        return
    host = hosts[0]
    host_id = host["policy_id"]

    for add_on in add_ons:
        ids = {"host": host_id, "add_on": add_on["policy_id"]}
        for table, owner in (("trip_policies", "trip_id"), ("user_saved_policies", "user_id")):
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET policy_id = :host WHERE policy_id = :add_on "
                    f"AND {owner} NOT IN (SELECT {owner} FROM {table} WHERE policy_id = :host)"
                ),
                ids,
            )
            bind.execute(sa.text(f"DELETE FROM {table} WHERE policy_id = :add_on"), ids)
        bind.execute(sa.text("UPDATE policies SET status = 'hidden' WHERE id = :add_on"), ids)
    bind.execute(
        sa.text(
            "UPDATE external_source_records SET freshness_status = 'stale' "
            "WHERE source_category = :category AND canonical_key = :key"
        ),
        {"category": SOURCE_CATEGORY, "key": ADD_ON_KEY},
    )

    payload = host["raw_payload"]
    if isinstance(payload, str):  # sqlite 는 JSON 을 문자열로 돌려준다
        payload = json.loads(payload)
    record = SimpleNamespace(
        title=host["title"],
        benefit_text=host["benefit_text"],
        raw_payload=payload,
        source_category=host["source_category"],
        start_date=host["start_date"],
        end_date=host["end_date"],
        last_fetched_at=host["last_fetched_at"],
        created_at=None,
    )
    bind.execute(
        sa.text("UPDATE policies SET structured_detail = :detail, card_summary = :card WHERE id = :id").bindparams(
            sa.bindparam("detail", type_=postgres_json)
        ),
        {"detail": structured_detail_for_traffic(record), "card": HOST_CARD, "id": host_id},
    )


def downgrade() -> None:
    # 정책 · 기록 상태만 되돌린다. 옮긴 일정 · 저장 링크와 합친 상세는 그대로 둔다.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE external_source_records SET freshness_status = 'unknown' "
            "WHERE source_category = :category AND canonical_key = :key"
        ),
        {"category": SOURCE_CATEGORY, "key": ADD_ON_KEY},
    )
    bind.execute(
        sa.text(
            "UPDATE policies SET status = 'active' WHERE id IN ("
            "  SELECT p.id FROM policies p JOIN external_source_records r ON r.id = p.external_source_record_id"
            "  WHERE r.source_category = :category AND r.canonical_key = :key)"
        ),
        {"category": SOURCE_CATEGORY, "key": ADD_ON_KEY},
    )
