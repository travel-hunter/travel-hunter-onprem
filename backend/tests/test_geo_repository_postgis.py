import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.repositories import geo as geo_repository

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGIS_TESTS") != "1", reason="set RUN_POSTGIS_TESTS=1 and POSTGIS_TEST_DATABASE_URL")

# 0050 과 같은 모양(마이그레이션은 앱 코드를 들여오지 않으므로 여기 다시 적는다)
SHAPE = ("id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
         "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, geom geometry(Geometry, 5186) NOT NULL")
DDL = [
    "CREATE EXTENSION IF NOT EXISTS postgis", "DROP SCHEMA IF EXISTS geo CASCADE", "CREATE SCHEMA geo", "CREATE SEQUENCE geo.feature_id_seq",
    f"CREATE TABLE geo.building ({SHAPE})", f"CREATE TABLE geo.parcel ({SHAPE}, jimok varchar(4))",
    "CREATE TABLE geo.legal_dong (code varchar(10) PRIMARY KEY, name varchar(100) NOT NULL)",
]
CENTER = "st_transform(st_setsrid(st_makepoint(126.9780, 37.5665), 4326), 5186)"
EDGE = (37.5665, 126.9790)   # (위도, 경도) 시청 동쪽 약 90m, 400m 땅 안 - 아래 둘째 건물 B2 의 북쪽 변 위에 놓는 점


def refuse_app_database(session: Session) -> None:
    """이 픽스처는 geo 스키마를 통째로 지운다 - 앱 DB(public.alembic_version 이 있다)나 월 적재가 끝난 DB(geo.building 에 행이 있다)에는 돌리지 않는다."""

    if session.execute(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")).scalar():
        pytest.fail("POSTGIS_TEST_DATABASE_URL 의 DB 에 public.alembic_version 이 있다 - 앱 DB 다. 시험이 geo 스키마를 지우므로 빈 시험 DB 를 쓸 것")
    if session.execute(text("SELECT to_regclass('geo.building') IS NOT NULL")).scalar() and session.execute(text("SELECT EXISTS (SELECT 1 FROM geo.building)")).scalar():
        pytest.fail("POSTGIS_TEST_DATABASE_URL 의 geo.building 에 적재된 행이 있다 - 시험이 geo 스키마를 지우므로 빈 시험 DB 를 쓸 것")


@pytest.fixture
def db():
    engine = create_engine(os.environ["POSTGIS_TEST_DATABASE_URL"])
    with Session(engine) as session:
        refuse_app_database(session)
        for statement in DDL:
            session.execute(text(statement))
        # 서울시청 둘레 TM(EPSG:5186) 정사각형: 건물 20m, 그 건물을 품는 땅 400m
        session.execute(text(f"INSERT INTO geo.building (feature_key, pnu, la, lo, rx, ry, geom) SELECT 'B1', '1114010300100310000', 37.5665, 126.9780, st_x(p), st_y(p), st_expand(p, 10) FROM (SELECT {CENTER} p) c"))
        session.execute(text(f"INSERT INTO geo.parcel (feature_key, pnu, la, lo, rx, ry, geom, jimok) SELECT '1114010300100310000', '1114010300100310000', 37.5665, 126.9780, st_x(p), st_y(p), st_expand(p, 200), '대' FROM (SELECT {CENTER} p) c"))
        # 경계 시험용 둘째 건물 B2: 시험 점(EDGE)을 locate 와 같은 식(4326 점 → st_transform 5186)으로 옮긴 점 e 가 북쪽 변 위에 정확히 놓이게 짠다.
        # 위도만 뽑아 경도를 리터럴로 다시 넣고 왕복 변환하면 y 가 부동소수 오차만큼 변에서 벗어난다 - 같은 입력은 같은 double 이다
        session.execute(
            text("INSERT INTO geo.building (feature_key, pnu, la, lo, rx, ry, geom) SELECT 'B2', '1114010300100310000', :lat, :lng, st_x(e), st_y(e) - 10, st_makeenvelope(st_x(e) - 10, st_y(e) - 20, st_x(e) + 10, st_y(e), 5186) FROM (SELECT st_transform(st_setsrid(st_makepoint(:lng, :lat), 4326), 5186) e) c"),
            {"lat": EDGE[0], "lng": EDGE[1]},
        )
        session.execute(text("INSERT INTO geo.legal_dong VALUES ('1114010300', '서울특별시 중구 태평로1가')"))
        session.commit()
        yield session
        session.execute(text("DROP SCHEMA geo CASCADE"))
        session.commit()


def test_inside_on_the_edge_far_inside_the_parcel_and_at_sea(db) -> None:
    inside, edge, parcel_far, sea = geo_repository.locate(db, [(37.5665, 126.9780), EDGE, (37.5675, 126.9780), (37.0, 125.0)])
    assert (inside.kind, inside.address) == ("building", "서울특별시 중구 태평로1가 31")
    assert edge.kind == "building" and abs(edge.distance_m - 10) < 0.001   # ST_Covers: 변 위의 점도 그 건물(ST_Contains 였다면 400m 땅이 나온다). 대표점은 변에서 10m 남쪽
    assert parcel_far.kind == "parcel" and 100 < parcel_far.distance_m < 120   # 약 111m 북쪽 - 30m 밖이라 주소만
    assert sea is None
    assert geo_repository.get_by_ref(db, "building", inside.id).address == inside.address
    assert geo_repository.get_by_ref(db, "parcel", inside.id) is None   # 같은 id 라도 종류가 다르면 없다


def test_a_failed_geo_lookup_on_postgres_rolls_back_only_to_the_savepoint(db) -> None:
    # Postgres 는 실패한 문장 뒤 같은 트랜잭션의 질의를 모두 막는다(InFailedSqlTransaction). SAVEPOINT 가 저장 · locate 의 요청을 살리는지 본다
    from app.schemas.trip import GeoRef
    from app.services import address_fill
    from app.services import trips as trip_service

    db.execute(text("DROP SCHEMA geo CASCADE"))   # 이 트랜잭션 안에서만 - 아래 finally 의 rollback 이 되돌린다
    try:
        with pytest.raises(trip_service.TripServiceError) as unavailable:
            trip_service._geo_ref_hit(db, GeoRef(kind="parcel", id=1, pin=True))
        assert unavailable.value.status_code == 503
        assert address_fill.locate(db, 37.5665, 126.9780) == {"fill": None, "nearCenter": False}
        assert db.execute(text("SELECT 1")).scalar() == 1   # 바깥 트랜잭션이 아직 쓸 수 있다
    finally:
        db.rollback()   # 단언이 실패해도 geo 스키마를 되살려, 픽스처 정리의 DROP SCHEMA 가 진짜 실패를 가리지 않게 한다
