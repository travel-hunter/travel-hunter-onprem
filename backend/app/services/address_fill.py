"""주소 채움(방식1) - 맞춰 본 줄 가운데 우리 장소 목록과 바로 맞지 않는 줄에 건물 · 땅 지번을 붙인다.
받은 좌표(카카오 좌표 · 찍은 좌표)는 질의에만 쓰고 버린다(데브톡 151505-1 · 151842). 실패해도 검색은 보인다 - fill 이 비고 화면은 위치 찍기로 간다.
조회는 SAVEPOINT 안에서 한다 - Postgres 는 실패한 문장 뒤 같은 트랜잭션의 다음 질의를 모두 막는다."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories import geo as geo_repository
from app.services.geo_reference import fill_item, within_gate
from app.services.public_places import PlaceMatchInput

logger = logging.getLogger(__name__)


def with_fill(db: Session, rows: Sequence[PlaceMatchInput | None], answers: list[dict[str, object] | None]) -> list[dict[str, object] | None]:
    for answer in answers:
        if answer is not None:
            answer["fill"] = None
    wanted = [i for i, (row, answer) in enumerate(zip(rows, answers)) if row is not None and answer is not None and answer["result"] != "match"]
    if not wanted:
        return answers
    try:
        with db.begin_nested():
            hits = geo_repository.locate(db, [(rows[i].latitude, rows[i].longitude) for i in wanted])
    except Exception as error:   # ponytail: 검색에 덧붙이는 정보라 무엇이 터져도 검색은 살린다(저장 · locate 는 SQLAlchemyError 만 잡는다)
        logger.warning("place_fill_failed error=%s", type(error).__name__)
        return answers
    for i, hit in zip(wanted, hits):
        answers[i]["fill"] = fill_item(hit) if hit is not None and within_gate(hit) else None
    return answers


def locate(db: Session, latitude: float, longitude: float) -> dict[str, object]:
    try:
        with db.begin_nested():
            (hit,) = geo_repository.locate(db, [(latitude, longitude)])
    except SQLAlchemyError as error:   # geo 표가 없거나 DB 가 실패 - 지번 없음과 같게. 코드 결함은 올린다
        logger.warning("place_locate_failed error=%s", type(error).__name__)
        return {"fill": None, "nearCenter": False}
    if hit is None:
        return {"fill": None, "nearCenter": False}
    return {"fill": fill_item(hit), "nearCenter": within_gate(hit)}
