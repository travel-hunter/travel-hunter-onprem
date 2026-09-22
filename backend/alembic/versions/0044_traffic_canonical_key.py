"""re-key traffic_benefit source records by title so recollection updates the same policy

Revision ID: 0044_traffic_canonical_key
Revises: 0043_policy_card_summary
Create Date: 2026-09-22

The traffic parser used to hash title + period + benefit text into canonical_key, so any change in the
scraped wording (cleanup, a new date) produced a brand-new policy next to the old one. The key is now
hash(source_category | core title). This migration moves existing traffic_benefit rows onto the new key:

- a row that has a published policy attached keeps its id, slug, policy id and user links; only
  canonical_key / external_id change
- rows that share the new key with such a row and have no policy are leftovers of earlier scrapes and
  are deleted (review candidates on them go too)
- rows with no policy and no collision are simply re-keyed

Downgrade cannot restore the old keys (they were hashes of scraped text that is no longer identical),
so it is a no-op that leaves the title-based keys in place.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.travelmonth_traffic_parser import traffic_canonical_key


revision: str = "0044_traffic_canonical_key"
down_revision: str | None = "0043_policy_card_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_CATEGORY = "traffic_benefit"


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT r.id, r.title, r.canonical_key, "
            "       EXISTS (SELECT 1 FROM policies p WHERE p.external_source_record_id = r.id) AS has_policy "
            "FROM external_source_records r WHERE r.source_category = :category ORDER BY r.id"
        ),
        {"category": SOURCE_CATEGORY},
    ).mappings().all()
    if not rows:
        return

    # 새 key 별로 남길 행 하나를 고른다 - 정책이 붙은 행이 우선, 없으면 가장 오래된 행
    keeper_by_key: dict[str, int] = {}
    for row in rows:
        new_key = traffic_canonical_key(row["title"])
        current = keeper_by_key.get(new_key)
        if current is None:
            keeper_by_key[new_key] = row["id"]
            continue
        current_has_policy = next(r["has_policy"] for r in rows if r["id"] == current)
        if row["has_policy"] and not current_has_policy:
            keeper_by_key[new_key] = row["id"]

    keep_ids = set(keeper_by_key.values())
    for row in rows:
        new_key = traffic_canonical_key(row["title"])
        if row["id"] in keep_ids:
            if row["canonical_key"] != new_key:
                bind.execute(
                    sa.text(
                        "UPDATE external_source_records SET canonical_key = :key, external_id = :key WHERE id = :id"
                    ),
                    {"key": new_key, "id": row["id"]},
                )
        else:
            # 같은 정책의 옛 수집 잔여물. 정책이 붙어 있으면 여기 오지 않는다(위에서 keeper 가 된다).
            bind.execute(
                sa.text("DELETE FROM policy_review_candidates WHERE external_source_record_id = :id"),
                {"id": row["id"]},
            )
            bind.execute(sa.text("DELETE FROM external_source_records WHERE id = :id"), {"id": row["id"]})


def downgrade() -> None:
    # 옛 key 는 수집 원문의 해시라 되살릴 수 없다. 제목 기반 key 를 그대로 둔다.
    pass
