"""fill structured detail for the nationwide travelmonth traffic policies

Revision ID: 0045_traffic_detail
Revises: 0044_traffic_canonical_key
Create Date: 2026-09-22

교통 혜택 11건은 매퍼가 없어 structured_detail 이 비어 있었다. 매퍼(policy_semantic_mapping.
_traffic_benefit)를 새로 붙였지만 상세 지문(_detail_fingerprint_payload)은 레코드만 보므로
재수집만으로는 후보가 생기지 않는다. 이미 공개된 행은 여기서 한 번 채운다.

검토 흐름 밖에서 공개 정책 행을 쓴다. 문장은 전부 사람이 확인·승인한 것이고, 선례는
0032_dgtour_structured_detail 이다. 이후 사이트가 바뀌면 후보 → 승인 → 재승격 경로가
같은 매퍼를 다시 태우므로 이 마이그레이션은 한 번만 필요하다.

정책 id · slug · 사용자 링크는 건드리지 않는다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

from app.models.tables import postgres_json
from app.services.travelmonth_traffic_detail import structured_detail_for_traffic


revision: str = "0045_traffic_detail"
down_revision: str | None = "0044_traffic_canonical_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_CATEGORY = "traffic_benefit"

_SELECT = sa.text(
    "SELECT p.id AS policy_id, p.official_url, r.title, r.benefit_text, r.raw_payload, "
    "       r.source_category, r.start_date, r.end_date, r.last_fetched_at, r.collected_page_url "
    "FROM policies p JOIN external_source_records r ON r.id = p.external_source_record_id "
    "WHERE r.source_category = :category ORDER BY p.id"
)

_UPDATE_DETAIL = sa.text(
    "UPDATE policies SET structured_detail = :detail WHERE id = :id"
).bindparams(sa.bindparam("detail", type_=postgres_json))

_UPDATE_URL = sa.text("UPDATE policies SET official_url = :url WHERE id = :id")


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(_SELECT, {"category": SOURCE_CATEGORY}).mappings().all()
    for row in rows:
        payload = row["raw_payload"]
        if isinstance(payload, str):  # sqlite 는 JSON 을 문자열로 돌려준다
            payload = json.loads(payload)
        record = SimpleNamespace(
            title=row["title"],
            benefit_text=row["benefit_text"],
            raw_payload=payload,
            source_category=row["source_category"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            last_fetched_at=row["last_fetched_at"],
            created_at=None,
        )
        bind.execute(_UPDATE_DETAIL, {"detail": structured_detail_for_traffic(record), "id": row["policy_id"]})
        # "#" 은 링크가 아니다. 파서가 이제 걸러내지만 이미 저장된 행은 여기서 출처 페이지로 돌린다.
        if (row["official_url"] or "").strip() == "#" and row["collected_page_url"]:
            bind.execute(_UPDATE_URL, {"url": row["collected_page_url"], "id": row["policy_id"]})

    # 카드 문구에서 근거 없는 "(4인)" 추론을 지운다. 파서에서도 함께 제거했다.
    bind.execute(
        sa.text(
            "UPDATE policies SET card_summary = replace(card_summary, '(4인)', '') "
            "WHERE source_category = :category AND card_summary LIKE '%(4인)%'"
        ),
        {"category": SOURCE_CATEGORY},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE policies SET structured_detail = NULL WHERE id IN ("
            "  SELECT p.id FROM policies p JOIN external_source_records r"
            "    ON r.id = p.external_source_record_id WHERE r.source_category = :category)"
        ),
        {"category": SOURCE_CATEGORY},
    )
