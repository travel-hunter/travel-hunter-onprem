import os

import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_POSTGIS_TESTS") != "1", reason="set RUN_POSTGIS_TESTS=1 and POSTGIS_TEST_DATABASE_URL")
pyogrio = pytest.importorskip("pyogrio")
shapely = pytest.importorskip("shapely")
psycopg = pytest.importorskip("psycopg")

from app.services.geo_reference import EXPECTED_REGION_CODES  # noqa: E402
from scripts.geo_load import LoadBusy, exclusive_load, load, run, source_crs_problem  # noqa: E402

URL = os.environ.get("POSTGIS_TEST_DATABASE_URL", "").replace("postgresql+psycopg://", "postgresql://")
LAT, LNG = 37.5665, 126.9780


def connect():
    return psycopg.connect(URL)


def refuse_app_database(c) -> None:
    """이 파일의 픽스처는 geo 스키마를 통째로 지운다 - 앱 DB(public.alembic_version 이 있다)나 월 적재가 끝난 DB(geo.building 에 행이 있다)에는 돌리지 않는다."""

    c.execute("SELECT to_regclass('public.alembic_version') IS NOT NULL")
    if c.fetchone()[0]:
        pytest.fail("POSTGIS_TEST_DATABASE_URL 의 DB 에 public.alembic_version 이 있다 - 앱 DB 다. 시험이 geo 스키마를 지우므로 빈 시험 DB 를 쓸 것")
    c.execute("SELECT to_regclass('geo.building') IS NOT NULL")
    if c.fetchone()[0]:
        c.execute("SELECT EXISTS (SELECT 1 FROM geo.building)")
        if c.fetchone()[0]:
            pytest.fail("POSTGIS_TEST_DATABASE_URL 의 geo.building 에 적재된 행이 있다 - 시험이 geo 스키마를 지우므로 빈 시험 DB 를 쓸 것")


def write_square(path, crs: str, dong_name: str = "서울특별시 중구 태평로1가") -> None:
    import numpy as np
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(LNG, LAT)
    square = shapely.box(x - 10, y - 10, x + 10, y + 10)
    pyogrio.raw.write(str(path), geometry=np.array([shapely.to_wkb(square)], dtype=object),
                      field_data=[np.array(["0000000000000000000000000001"], dtype=object), np.array(["1114010300100310000"], dtype=object),
                                  np.array(["1114010300"], dtype=object), np.array([dong_name], dtype=object)],
                      fields=["A1", "A2", "A3", "A4"], geometry_type="Polygon", crs=crs, driver="ESRI Shapefile", encoding="cp949")


@pytest.fixture
def cur():
    with psycopg.connect(URL, autocommit=True) as conn, conn.cursor() as c:
        refuse_app_database(c)
        c.execute("CREATE EXTENSION IF NOT EXISTS postgis; DROP SCHEMA IF EXISTS geo CASCADE; CREATE SCHEMA geo; CREATE SEQUENCE geo.feature_id_seq;")
        c.execute("CREATE TABLE geo.building_next (id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
                  "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, geom geometry(Geometry, 5186) NOT NULL)")
        yield c
        c.execute("DROP SCHEMA geo CASCADE")


def test_5186_and_5174_shapefiles_land_where_their_lat_lng_says_and_a_wrong_crs_is_refused(tmp_path, cur) -> None:
    tm, bessel, web = tmp_path / "AL_D010_11_20260909.shp", tmp_path / "AL_D010_26_20260909.shp", tmp_path / "AL_D010_27_20260909.shp"
    write_square(tm, "EPSG:5186")
    write_square(bessel, "EPSG:5174")   # 2023-08 이전 판의 좌표계 - 5186 으로 바꿔 넣는다
    write_square(web, "EPSG:3857")
    assert source_crs_problem(str(tm)) is None and source_crs_problem(str(bessel)) is None and "EPSG:3857" in source_crs_problem(str(web))
    dongs, prefixes = {}, set()
    assert load(cur, "building", [str(tm), str(bessel)], dongs, prefixes) == (2, 0, 0, 0)
    cur.execute("SELECT st_srid(geom), la, lo, st_y(st_transform(st_centroid(geom), 4326)), st_x(st_transform(st_centroid(geom), 4326)) FROM geo.building_next ORDER BY id")
    for srid, la, lo, glat, glng in cur.fetchall():
        assert srid == 5186
        for value, expected in ((la, LAT), (lo, LNG), (glat, LAT), (glng, LNG)):
            assert abs(value - expected) < 1e-4   # 약 10m 안
    assert dongs == {"1114010300": "서울특별시 중구 태평로1가"} and prefixes == {"1114010300"}


def test_a_blank_or_whitespace_dong_name_counts_as_missing(tmp_path, cur) -> None:
    path = tmp_path / "AL_D010_11_20260909.shp"
    write_square(path, "EPSG:5186", dong_name="　")   # 전각 공백 - DBF 가 빈칸 채움으로 지우지 못한다
    dongs, prefixes = {}, set()
    assert load(cur, "building", [str(path)], dongs, prefixes) == (1, 0, 0, 0)
    assert dongs == {} and prefixes == {"1114010300"}   # 이름이 없는 코드로 남아 run 이 줄을 뺀다


def test_a_row_without_a_geometry_is_counted_not_loaded(tmp_path, cur) -> None:
    import numpy as np
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True).transform(LNG, LAT)
    path = tmp_path / "AL_D010_11_20260909.shp"
    pyogrio.raw.write(str(path), geometry=np.array([shapely.to_wkb(shapely.box(x - 10, y - 10, x + 10, y + 10)), None], dtype=object),
                      field_data=[np.array(["0000000000000000000000000001", "0000000000000000000000000002"], dtype=object), np.array(["1114010300100310000"] * 2, dtype=object),
                                  np.array(["1114010300"] * 2, dtype=object), np.array(["서울특별시 중구 태평로1가"] * 2, dtype=object)],
                      fields=["A1", "A2", "A3", "A4"], geometry_type="Polygon", crs="EPSG:5186", driver="ESRI Shapefile", encoding="cp949")
    assert load(cur, "building", [str(path)], {}, set()) == (1, 0, 0, 1)   # 둘째 줄은 도형이 없어 넣지 않고 센다
    cur.execute("SELECT count(*) FROM geo.building_next")
    assert cur.fetchone() == (1,)


def test_the_load_lock_stays_on_one_connection_across_commits_and_blocks_a_second_loader() -> None:
    with exclusive_load(connect) as (raw, pid):
        c = raw.cursor()
        c.execute("SELECT 1")
        raw.commit()
        c = raw.cursor()
        c.execute("SELECT pg_backend_pid(), count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid()")
        assert c.fetchone() == (pid, 1)   # commit 을 넘어 같은 연결 · 같은 잠금
        with pytest.raises(LoadBusy):
            with exclusive_load(connect):
                pass
    with exclusive_load(connect):   # 끝나면 풀렸다(unlock 이 true 였다)
        pass


SHAPE = ("id bigint PRIMARY KEY DEFAULT nextval('geo.feature_id_seq'), feature_key varchar(40) NOT NULL, pnu varchar(19) NOT NULL, "
         "la double precision NOT NULL, lo double precision NOT NULL, rx double precision NOT NULL, ry double precision NOT NULL, geom geometry(Geometry, 5186) NOT NULL")
SCHEMA_0050 = [   # 0050 의 geo 부분과 같은 모양
    "CREATE EXTENSION IF NOT EXISTS postgis", "DROP SCHEMA IF EXISTS geo CASCADE", "CREATE SCHEMA geo", "CREATE SEQUENCE geo.feature_id_seq",
    f"CREATE TABLE geo.building ({SHAPE})", f"CREATE TABLE geo.parcel ({SHAPE}, jimok varchar(4))",
    "CREATE INDEX building_geom_gix ON geo.building USING gist (geom)", "CREATE INDEX building_pnu_ix ON geo.building (pnu)",
    "CREATE INDEX parcel_geom_gix ON geo.parcel USING gist (geom)", "CREATE INDEX parcel_pnu_ix ON geo.parcel (pnu)",
    "CREATE TABLE geo.legal_dong (code varchar(10) PRIMARY KEY, name varchar(100) NOT NULL)",
    "CREATE TABLE geo.load_run (id bigserial PRIMARY KEY, finished_at timestamptz NOT NULL DEFAULT now(), building_rows bigint NOT NULL, "
    "parcel_rows bigint NOT NULL, building_base_date varchar(8), parcel_base_date varchar(8))",
]


@pytest.fixture
def geo_schema():
    with psycopg.connect(URL, autocommit=True) as conn, conn.cursor() as c:
        refuse_app_database(c)
        for statement in SCHEMA_0050:
            c.execute(statement)
        yield c
        c.execute("DROP SCHEMA geo CASCADE")


def write_shapes(path, points, fields: dict[str, list]) -> None:
    import numpy as np
    from pyproj import Transformer

    to_tm = Transformer.from_crs("EPSG:4326", "EPSG:5186", always_xy=True)
    boxes = [shapely.to_wkb(shapely.box(x - 8, y - 8, x + 8, y + 8)) for x, y in (to_tm.transform(lng, lat) for lat, lng in points)]
    path.parent.mkdir(parents=True, exist_ok=True)
    pyogrio.raw.write(str(path), geometry=np.array(boxes, dtype=object), field_data=[np.array(v, dtype=object) for v in fields.values()],
                      fields=list(fields), geometry_type="Polygon", crs="EPSG:5186", driver="ESRI Shapefile", encoding="cp949")


def write_month(root, building_date: str, parcel_date: str, *, blank_key_in: str | None = None, blank_name_in: str | None = None) -> None:
    """시도 16개 - 건물 한 동씩, 땅은 대지 하나 · 논 하나(논은 적재에서 빠진다)."""

    for n, code in enumerate(sorted(EXPECTED_REGION_CODES)):
        lat, lng, dong = 35.0 + n * 0.01, 127.0, f"{code}11010100"
        pnu = f"{dong}1{n + 1:04d}0000"
        key = None if code == blank_key_in else f"B{building_date}{code}"
        dong_name = None if code == blank_name_in else "시험시 시험동"
        write_shapes(root / "buildings" / f"AL_D010_{code}_{building_date}" / f"AL_D010_{code}_{building_date}.shp", [(lat, lng)],
                     {"A1": [key], "A2": [pnu], "A3": [dong], "A4": [dong_name]})
        write_shapes(root / "parcels" / f"AL_D002_{code}_{parcel_date}" / f"AL_D002_{code}_{parcel_date}.shp", [(lat, lng), (lat + 0.001, lng)],
                     {"A1": [pnu, pnu[:-4] + "0001"], "A2": [dong, dong], "A3": [dong_name] * 2, "A5": [f"{n + 1}대", f"{n + 1}-1답"]})


def test_run_checks_loads_swaps_and_never_reuses_ids(tmp_path, geo_schema) -> None:
    def go(root, accept: bool) -> int:
        return run(root / "buildings", root / "parcels", connect=connect, accept_row_count_change=accept)

    def state() -> tuple:
        geo_schema.execute("SELECT (SELECT count(*) FROM geo.building), (SELECT count(*) FROM geo.parcel), (SELECT count(*) FROM geo.legal_dong), "
                           "(SELECT count(*) FROM geo.load_run), (SELECT min(id) FROM geo.building), "
                           "(SELECT count(*) FROM pg_tables WHERE schemaname = 'geo' AND tablename LIKE '%_next'), "
                           "(SELECT count(*) FROM pg_locks WHERE locktype = 'advisory')")
        return geo_schema.fetchone()

    write_month(tmp_path / "bad", "20260909", "20260908", blank_key_in="11")
    assert go(tmp_path / "bad", True) == 3   # 식별자 빈 줄 1/16 - 품질 검사는 행 수 옵션으로 넘기지 못한다
    assert state()[5] == 0   # 거부해도 만들다 만 _next 표를 남기지 않는다
    write_month(tmp_path / "noname", "20260909", "20260908", blank_name_in="11")
    assert go(tmp_path / "noname", True) == 4   # 법정동 이름이 빠진 시도 - 행 수 옵션으로 넘기지 못한다
    assert state()[:4] == (0, 0, 0, 0) and state()[5] == 0
    write_month(tmp_path / "m1", "20260909", "20260908")
    assert go(tmp_path / "m1", False) == 8   # 시험 판은 16줄이라 행 수 범위 밖
    assert state()[:4] == (0, 0, 0, 0)   # 바꾸지 않았다
    assert state()[5] == 0   # 이것도 _next 를 남기지 않는다
    assert go(tmp_path / "m1", True) == 0
    first = state()
    assert first[:4] == (16, 16, 16, 1) and first[5:] == (0, 0)   # 논은 빠졌다 · _next 없음 · 잠금 풀림
    write_month(tmp_path / "m2", "20261009", "20261008")
    assert go(tmp_path / "m2", True) == 0
    second = state()
    assert second[:4] == (16, 16, 16, 2) and second[4] > first[4]   # 새 판은 새 id - 옛 geoRef 는 404 가 된다
    geo_schema.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'geo' ORDER BY 1")
    assert [row[0] for row in geo_schema.fetchall()] == [
        "building_geom_gix", "building_pkey", "building_pnu_ix", "legal_dong_pkey", "load_run_pkey", "parcel_geom_gix", "parcel_pkey", "parcel_pnu_ix",
    ]
    geo_schema.execute("SELECT building_base_date, parcel_base_date, jimok FROM geo.load_run, (SELECT DISTINCT jimok FROM geo.parcel) j ORDER BY geo.load_run.id")
    assert geo_schema.fetchall() == [("20260909", "20260908", "대"), ("20261009", "20261008", "대")]


def test_rows_of_a_dong_code_with_no_name_anywhere_are_left_out_when_they_are_under_the_limit(tmp_path, geo_schema, monkeypatch, capsys) -> None:
    monkeypatch.setattr("app.services.geo_reference.MAX_UNNAMED_DONG_RATIO", 0.5)   # 시험 판은 16줄이라 1줄이 6% 다
    write_month(tmp_path, "20260909", "20260908", blank_name_in="11")
    assert run(tmp_path / "buildings", tmp_path / "parcels", connect=connect, accept_row_count_change=True) == 0
    geo_schema.execute("SELECT (SELECT count(*) FROM geo.building), (SELECT count(*) FROM geo.building WHERE left(pnu, 10) = '1111010100'), "
                       "(SELECT count(*) FROM geo.parcel), (SELECT count(*) FROM geo.parcel WHERE left(pnu, 10) = '1111010100'), "
                       "(SELECT count(*) FROM geo.legal_dong), (SELECT count(*) FROM geo.legal_dong WHERE code = '1111010100'), "
                       "(SELECT building_rows FROM geo.load_run), (SELECT parcel_rows FROM geo.load_run), "
                       "(SELECT count(*) FROM pg_tables WHERE schemaname = 'geo' AND tablename LIKE '%_next')")
    assert geo_schema.fetchone() == (15, 0, 15, 0, 15, 0, 15, 15, 0)   # 이름 없는 코드의 줄만 빠졌고, load_run 은 뺀 뒤의 줄 수다
    out = capsys.readouterr().out
    assert "building: 법정동 이름 없는 코드 1개 · 뺀 줄 1" in out and "parcel: 법정동 이름 없는 코드 1개 · 뺀 줄 1" in out


def test_a_swap_that_cannot_get_its_lock_exits_6_and_drops_the_new_tables(tmp_path, geo_schema, monkeypatch) -> None:
    monkeypatch.setattr("scripts.geo_load.SWAP_LOCK_TIMEOUT", "100ms")
    monkeypatch.setattr("scripts.geo_load.time.sleep", lambda _seconds: None)
    write_month(tmp_path, "20260909", "20260908")
    with psycopg.connect(URL) as reader:   # 읽는 쪽이 옛 표를 쥐고 있어 이름 바꾸기가 잠금을 얻지 못한다
        reader.execute("SELECT count(*) FROM geo.building")
        assert run(tmp_path / "buildings", tmp_path / "parcels", connect=connect, accept_row_count_change=True) == 6
    geo_schema.execute("SELECT (SELECT count(*) FROM geo.load_run), (SELECT count(*) FROM pg_tables WHERE schemaname = 'geo' AND (tablename LIKE '%_next' OR tablename LIKE '%_old'))")
    assert geo_schema.fetchone() == (0, 0)   # 바꾸지 않았고, 만들다 만 표도 없다


def test_any_failure_after_loading_started_drops_the_new_tables_and_releases_the_lock(tmp_path, geo_schema, monkeypatch) -> None:
    import scripts.geo_load as geo_load

    real_load, calls = geo_load.load, []

    def fail_on_the_second_table(*args, **kwargs):
        calls.append(args[1])
        if len(calls) == 2:   # 건물 표는 다 채워 확정했고 땅 표를 채우다 죽는다
            raise RuntimeError("boom")
        return real_load(*args, **kwargs)

    monkeypatch.setattr(geo_load, "load", fail_on_the_second_table)
    write_month(tmp_path, "20260909", "20260908")
    with pytest.raises(RuntimeError, match="boom"):   # 원래 오류가 그대로 올라온다
        run(tmp_path / "buildings", tmp_path / "parcels", connect=connect, accept_row_count_change=True)
    assert calls == ["building", "parcel"]
    geo_schema.execute("SELECT (SELECT count(*) FROM pg_tables WHERE schemaname = 'geo' AND (tablename LIKE '%_next' OR tablename LIKE '%_old')), "
                       "(SELECT count(*) FROM geo.load_run), (SELECT count(*) FROM pg_locks WHERE locktype = 'advisory')")
    assert geo_schema.fetchone() == (0, 0, 0)   # 수 GB 짜리 _next 를 남기지 않았고, 바꾸지 않았고, 잠금도 풀렸다


def test_an_unreadable_shp_is_a_structural_problem_not_a_traceback(tmp_path, capsys) -> None:
    def no_db():
        raise AssertionError("connected")

    write_month(tmp_path, "20260909", "20260908")
    broken = tmp_path / "buildings" / "AL_D010_11_20260909" / "AL_D010_11_20260909.shp"
    broken.write_bytes(b"this is not a shapefile")
    assert run(tmp_path / "buildings", tmp_path / "parcels", connect=no_db, accept_row_count_change=True) == 3   # 이름은 다 맞다 - 열 수 없는 파일이 걸린다
    assert "AL_D010_11_20260909.shp: unreadable (" in capsys.readouterr().err
