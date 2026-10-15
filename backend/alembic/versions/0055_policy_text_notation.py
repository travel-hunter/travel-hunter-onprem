"""fix notation errors in stored policy detail text

Revision ID: 0055_policy_text_notation
Revises: 0054_traffic_section_banners
Create Date: 2026-10-15

정책 상세의 표기 오류를 고친다(2026-10-15 사용자 결정 - 문체는 그대로, 표기만). 코드는 같은 PR 에서
고쳤고, 이 마이그레이션은 이미 저장된 행을 맞춘다. 매퍼 문장은 검토 대기열 지문에 들어가지 않아 재수집으로는
안 바뀐다(선례 0034 · 0045). 수집 기록(external_source_records)은 건드리지 않는다 - 지문이 그대로라 후보가
새로 생기지 않는다.

1. 글자 쌍(아래 NOTATION_FIXES): structured_detail 안 문자열과 target_condition 에 적용한다. 쌍은 여기 고정한다.
2. 반값여행에서 괄호 안 쉼표 · 가운뎃점까지 잘라 저장된 행('여행유형(가족' / '청년) …'): 조각 일부가 빠지거나
   다른 칸으로 가 있어 이어 붙이면 틀린다. 고친 매퍼로 그 행을 기록에서 다시 만들어(0045 처럼 지금 매퍼를
   쓴다) 기간(periods)을 뺀 칸을 바꾼다. 기간은 저장값을 둔다 - 지금 매퍼가 옛 행의 '여행 기간' 을 다시 만들지
   못하는 경우가 있다(2026-10-15 로컬 미리 계산). target_condition 은 그것도 잘렸을 때만 바꾼다.

admin_override_enabled 행은 사람이 고친 것이라 건드리지 않는다. 정책 id · slug · 상태 · 사용자 링크는 그대로.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from types import SimpleNamespace

import sqlalchemy as sa
from alembic import op

from app.models.tables import postgres_json
from app.services.policy_semantic_mapping import map_external_source_semantics


revision: str = "0055_policy_text_notation"
down_revision: str | None = "0054_traffic_section_banners"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("digital_tourism_resident_card", "stay_discount", "traffic_benefit", "local_half_trip")
HALF_TRIP = "local_half_trip"

# (틀린 표기, 고친 표기). 새 표기 안에 옛 표기가 없어 두 번 돌려도 같다.
NOTATION_FIXES: tuple[tuple[str, str], ...] = (
    (
        "VisitKorea/대한민국 구석구석에서 디지털관광주민증을 발급하고 제휴처에서 제시해야 합니다.",
        "VisitKorea(대한민국 구석구석)에서 디지털관광주민증을 발급받고 제휴처에서 제시해야 합니다.",
    ),
    ("디지털관광주민증을 발급한 여행자", "디지털관광주민증을 발급받은 여행자"),
    ("숙박세일페스타 대상 지역", "숙박세일 페스타 대상 지역"),
    ("인구감소지역(89개) 소재 관광지", "인구감소지역(89곳) 소재 관광지"),
    ("공사 디지털 관광 주민증 사용 시", "한국관광공사 디지털관광주민증 사용 시"),
    ("테마열차의 운임료를 50% 할인합니다.", "테마열차의 운임을 50% 할인합니다."),
    ("해당 시 / 군 / 구 목록은", "해당 시 · 군 · 구 목록은"),
)

_POLICIES = sa.text(
    "SELECT id, source_category, external_source_record_id, target_condition, structured_detail "
    "FROM policies WHERE source_category IN :categories AND NOT COALESCE(admin_override_enabled, false) "
    "ORDER BY id"
).bindparams(sa.bindparam("categories", expanding=True))

_RECORD = sa.text("SELECT * FROM external_source_records WHERE id = :id")

_UPDATE = sa.text(
    "UPDATE policies SET structured_detail = :detail, target_condition = :target, updated_at = CURRENT_TIMESTAMP "
    "WHERE id = :id"
).bindparams(sa.bindparam("detail", type_=postgres_json))


def fix_notation(text: str) -> str:
    for wrong, right in NOTATION_FIXES:
        text = text.replace(wrong, right)
    return text


def _fix_value(value: object) -> object:
    if isinstance(value, str):
        return fix_notation(value)
    if isinstance(value, list):
        return [_fix_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _fix_value(item) for key, item in value.items()}
    return value


def has_cut_parentheses(detail: object) -> bool:
    """괄호가 짝이 안 맞는 항목이 있으면 괄호 안에서 잘린 것이다. 개수가 같아도 ') … (' 처럼 닫는 괄호가
    먼저 나오면 잘린 조각이다."""
    if isinstance(detail, str):
        depth = 0
        for char in detail:
            depth += {"(": 1, "（": 1, ")": -1, "）": -1}.get(char, 0)
            if depth < 0:
                return True
        return depth != 0
    if isinstance(detail, list):
        return any(has_cut_parentheses(item) for item in detail)
    if isinstance(detail, dict):
        return any(has_cut_parentheses(item) for item in detail.values())
    return False


KEEP_STORED_SECTIONS = ("periods",)


def rebuilt_cut_sections(stored: dict, remapped: dict) -> dict:
    """기간을 뺀 칸을 다시 만든 것으로 바꾼다. 이어진 문장이 원래와 다른 칸(비고 → 필요 서류)으로 갈 수 있어
    잘린 칸만 바꾸면 조각이 남거나 새 항목이 빠진다. 기간은 저장값을 둔다(위 docstring)."""
    rebuilt = dict(stored)
    rebuilt.update({section: items for section, items in remapped.items() if section not in KEEP_STORED_SECTIONS})
    return rebuilt


def _json(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value  # sqlite 는 JSON 을 문자열로 돌려준다


def _remapped(bind: sa.Connection, record_id: int | None) -> tuple[object, str | None] | None:
    if record_id is None:
        return None
    row = bind.execute(_RECORD, {"id": record_id}).mappings().first()
    if row is None:
        return None
    fields = dict(row)
    fields["raw_payload"] = _json(fields.get("raw_payload"))
    if isinstance(fields.get("last_fetched_at"), str):
        fields["last_fetched_at"] = datetime.fromisoformat(fields["last_fetched_at"])
    mapping = map_external_source_semantics(SimpleNamespace(**fields))
    return mapping.structured_detail, mapping.target_condition


def planned_changes(bind: sa.Connection) -> list[tuple[dict, object, object]]:
    """(정책 행, 새 structured_detail, 새 target_condition) - 바뀌는 행만. 쓰지 않는다(미리 계산에도 쓴다)."""
    found = bind.execute(_POLICIES, {"categories": list(CATEGORIES)})
    if found is None:  # --sql(오프라인)은 읽을 행이 없다 - 데이터 정리는 실제 DB 에서만
        return []
    changes = []
    for row in found.mappings().all():
        detail = _json(row["structured_detail"])
        target = row["target_condition"]
        new_detail, new_target = detail, target
        if row["source_category"] == HALF_TRIP and has_cut_parentheses(detail):
            remapped = _remapped(bind, row["external_source_record_id"])
            if remapped is not None:
                new_detail = rebuilt_cut_sections(detail, remapped[0])
                new_target = remapped[1] if has_cut_parentheses(target) else target
        new_detail = _fix_value(new_detail)
        new_target = fix_notation(new_target) if isinstance(new_target, str) else new_target
        if new_detail != detail or new_target != target:
            changes.append((dict(row), new_detail, new_target))
    return changes


def upgrade() -> None:
    bind = op.get_bind()
    for row, detail, target in planned_changes(bind):
        bind.execute(_UPDATE, {"id": row["id"], "detail": detail, "target": target})


def downgrade() -> None:
    # 표기 교정이라 되돌리지 않는다
    pass
