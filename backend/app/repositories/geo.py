"""geo 스키마(건물 · 땅 지번) 읽기 - PostGIS 공간 색인. 받은 좌표(카카오 좌표 · 찍은 좌표)는 질의에만 쓰고 저장 · 로그하지 않는다."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.geo_reference import TABLES, GeoHit, GeoKind, jibun_address

# 6곳을 질의 한 번에: 건물이 품으면(경계 포함) 건물, 아니면 땅. 거리는 대표점까지(30m 판정은 부르는 쪽). 겹치면 id 가 작은 것 하나
LOCATE_SQL = text("""
WITH p AS (
  SELECT i, st_transform(st_setsrid(st_makepoint(x, y), 4326), 5186) AS pt
  FROM unnest(CAST(:xs AS float8[]), CAST(:ys AS float8[])) WITH ORDINALITY AS t(x, y, i)
), b AS (
  SELECT DISTINCT ON (p.i) p.i, 'building' AS kind, g.id, g.pnu, g.la, g.lo, sqrt(power(g.rx - st_x(p.pt), 2) + power(g.ry - st_y(p.pt), 2)) AS d
  FROM p JOIN geo.building g ON st_covers(g.geom, p.pt) ORDER BY p.i, g.id
), q AS (
  SELECT DISTINCT ON (p.i) p.i, 'parcel' AS kind, g.id, g.pnu, g.la, g.lo, sqrt(power(g.rx - st_x(p.pt), 2) + power(g.ry - st_y(p.pt), 2)) AS d
  FROM p JOIN geo.parcel g ON st_covers(g.geom, p.pt)
  WHERE NOT EXISTS (SELECT 1 FROM b WHERE b.i = p.i) ORDER BY p.i, g.id
), hit AS (SELECT * FROM b UNION ALL SELECT * FROM q)
SELECT hit.i, hit.kind, hit.id, hit.pnu, hit.la, hit.lo, hit.d, d.name
FROM hit LEFT JOIN geo.legal_dong d ON d.code = substr(hit.pnu, 1, 10)
ORDER BY hit.i
""")


SET_TIMEOUT_SQL = text("SELECT set_config('statement_timeout', :value, true)")   # true: 이 트랜잭션 안에서만


def _table(kind: GeoKind) -> str:
    if kind not in TABLES:
        raise ValueError(f"unknown geo kind: {kind}")
    return f"geo.{kind}"


def locate(db: Session, points: Sequence[tuple[float, float]], *, timeout_ms: int | None = None) -> list[GeoHit | None]:
    """(위도, 경도) 마다 품은 건물 · 땅. 없으면 None. 순서는 points 그대로.
    timeout_ms 를 주면 이 질의만 그 시간으로 끊는다(넘으면 Postgres 가 57014 로 끊는다 - 부르는 쪽이 SAVEPOINT 로 감싼다). 끝나면 앞 값을 되돌린다."""

    if not points:
        return []
    previous = None
    if timeout_ms is not None:
        previous = db.execute(text("SELECT current_setting('statement_timeout')")).scalar_one()
        db.execute(SET_TIMEOUT_SQL, {"value": str(timeout_ms)})
    rows = db.execute(LOCATE_SQL, {"ys": [lat for lat, _ in points], "xs": [lng for _, lng in points]}).all()
    if previous is not None:
        db.execute(SET_TIMEOUT_SQL, {"value": previous})
    hits: list[GeoHit | None] = [None] * len(points)
    for index, kind, feature_id, pnu, la, lo, distance, dong_name in rows:
        hits[index - 1] = GeoHit(kind, int(feature_id), pnu, jibun_address(dong_name or "", pnu), float(la), float(lo), float(distance))
    return hits


def get_by_ref(db: Session, kind: GeoKind, feature_id: int) -> GeoHit | None:
    """담을 때 - 화면이 보낸 참조(종류 · id)로 주소와 대표점을 다시 읽는다. 판이 바뀌어 사라졌으면 None."""

    row = db.execute(
        text(f"SELECT g.id, g.pnu, g.la, g.lo, d.name FROM {_table(kind)} g LEFT JOIN geo.legal_dong d ON d.code = substr(g.pnu, 1, 10) WHERE g.id = :id"),
        {"id": feature_id},
    ).first()
    if row is None:
        return None
    found_id, pnu, la, lo, dong_name = row
    return GeoHit(kind, int(found_id), pnu, jibun_address(dong_name or "", pnu), float(la), float(lo), 0.0)
