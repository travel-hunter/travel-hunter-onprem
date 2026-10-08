"""건물 · 땅 지번 월 적재(방식1) - 브이월드 전체데이터(시도별 SHP/ZIP)를 검사하고, geo.*_next 에 넣고, 한 트랜잭션에서 바꿔치기한다.

받는 법: 브이월드 'GIS건물통합정보'(AL_D010) · '연속지적도형정보'(AL_D002) 의 구분 '전체데이터' 최신 기준일, 시도 전부(로그인 필요 - 사람이 받는다).
실행: docker build --target geo-loader -t th-geo-loader backend
      docker run --rm --network <compose 네트워크> --env-file <backend 와 같은 env 파일> -v <받은 폴더>:/data:ro th-geo-loader \
        python scripts/geo_load.py --buildings /data/buildings --parcels /data/parcels
      (Windows 의 Git Bash 에서는 앞에 MSYS_NO_PATHCONV=1 - 안 붙이면 /data/... 가 Windows 경로로 바뀐다)
DB 는 앱 설정(DATABASE_URL)의 엔진에서 연결 하나를 빌려 끝까지 쥔다(advisory lock 이 그 연결에 붙는다). 출력은 건수 · 시간뿐이다.
구조 검사는 넘기지 못한다. 행 수 범위만 --accept-row-count-change 로 받아들인다. 서버에서 돌리는 것은 실행할 때마다 승인받는다.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
import zipfile
import zlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.services.geo_reference import (  # noqa: E402
    DATASET_OF, content_duplicate_problems, is_feature_key, is_pnu, jimok_of, keep_parcel, manifest_problems, quality_problems,
    row_count_problems, swap_statements, unnamed_dong_problems,
)

CHUNK = 200_000
DATE = re.compile(r"_(\d{8})")
LOCK_KEY = 7_201_008   # pg_try_advisory_lock - 적재 도구 하나만 돈다
SWAP_LOCK_TIMEOUT = "5s"
SWAP_TRIES = 3
UNREADABLE = (OSError, ValueError, RuntimeError, KeyError, EOFError, zlib.error, zipfile.BadZipFile)   # 파일을 열다 나는 오류 - pyogrio · pyproj(RuntimeError) · zip(BadZipFile · KeyError · 압축 본문이 깨지면 zlib.error · 잘리면 EOFError) · 읽기(OSError)
# 원본 칸 - 건물 A1 식별번호 · A2 고유번호 · A3 법정동코드 · A4 법정동명, 땅 A1 고유번호 · A2 법정동코드 · A3 법정동명 · A5 지번+지목(10/7 실파일 확인)
COLUMNS = {"building": {"key": "A1", "pnu": "A2", "code": "A3", "name": "A4", "jimok": None},
           "parcel": {"key": "A1", "pnu": "A1", "code": "A2", "name": "A3", "jimok": "A5"}}


class LoadBusy(Exception):
    """다른 적재가 같은 잠금을 쥐고 있다."""


class LockLost(Exception):
    """적재가 끝났을 때 연결이 바뀌었거나 잠금을 풀지 못했다."""


class UnreadableInput(Exception):
    """받은 파일을 열 수 없다(깨진 zip 등) - 구조 문제로 알리고 멈춘다. 메시지는 '<이름>: unreadable (<예외 종류>)'."""


def discover(root: Path) -> list[str]:
    """압축을 푼 폴더의 .shp(확장자 대소문자 무관), 그리고 푼 폴더가 없는 zip 안의 .shp. 열 수 없는 zip 은 UnreadableInput."""

    shp = sorted(str(p) for p in root.rglob("*") if p.suffix.lower() == ".shp")
    extracted = {Path(p).parent.name for p in shp}
    zipped: list[str] = []
    for zip_path in sorted(root.rglob("*.zip")):
        if zip_path.stem in extracted:
            continue
        try:
            with zipfile.ZipFile(zip_path) as zf:
                members = zf.namelist()
        except (zipfile.BadZipFile, OSError) as error:   # 받다 만 zip 은 흔하다 - 역추적 대신 구조 문제로
            raise UnreadableInput(f"{zip_path.name}: unreadable ({type(error).__name__})") from error
        zipped += [f"/vsizip/{zip_path.as_posix()}/{name}" for name in members if name.lower().endswith(".shp")]
    return shp + zipped


def base_date(paths: list[str]) -> str | None:
    dates = [m.group(1) for p in paths for m in [DATE.search(Path(p).name)] if m]
    return max(dates) if dates else None


def file_digest(path: str) -> str:
    """.shp 내용의 sha256 - '(2).shp'가 나눈 조각인지 같은 파일을 두 번 받은 것인지 내용으로 가린다."""

    digest = hashlib.sha256()
    if path.startswith("/vsizip/"):
        zip_path, member = path[len("/vsizip/"):].split(".zip/", 1)
        with zipfile.ZipFile(zip_path + ".zip") as zf, zf.open(member) as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    else:
        with open(path, "rb") as stream:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest()


def source_crs_problem(path: str) -> str | None:
    """좌표계 확인 - EPSG:5186 이면 그대로, 5174(2023-08 이전 판)는 load 가 5186 으로 바꾼다, 그 밖 · 없음은 멈춘다."""

    import pyogrio
    from pyproj import CRS

    raw = pyogrio.read_info(path).get("crs")
    if not raw:
        return f"{Path(path).name}: no CRS"
    epsg = CRS.from_user_input(raw).to_epsg()
    return None if epsg in (5186, 5174) else f"{Path(path).name}: unexpected CRS EPSG:{epsg}"


@contextmanager
def exclusive_load(connect: Callable[[], object]) -> Iterator[tuple[object, int]]:
    """연결 하나를 빌려 적재 끝까지 쥐고 advisory lock 을 건다. 잠금은 연결(세션)에 붙으므로 commit 을 여러 번 해도 같은 연결이어야 한다
    (풀에서 다시 빌리면 다른 연결이 될 수 있다 - 코덱스 재검토 HIGH). 끝날 때 같은 연결인지, 잠금이 풀렸는지 확인한다."""

    raw = connect()
    try:
        cur = raw.cursor()
        cur.execute("SELECT pg_backend_pid(), pg_try_advisory_lock(%s)", (LOCK_KEY,))
        pid, locked = cur.fetchone()
        raw.commit()
        if not locked:
            raise LoadBusy()
        try:
            yield raw, pid
        except BaseException:
            # 적재가 이미 실패하는 중이면 그 오류를 LockLost 로 가리지 않는다 - 잠금을 못 풀었다는 것만 알리고 원래 오류를 올린다
            try:
                released = _release(raw, pid)
            except Exception:
                released = False
            if not released:
                print("적재가 실패했고 잠금도 풀지 못했다 - pg_locks 를 확인할 것", file=sys.stderr)
            raise
        if not _release(raw, pid):
            raise LockLost()
    finally:
        raw.close()


def _release(raw, pid: int) -> bool:
    """advisory lock 을 풀고, 같은 연결에서 풀렸는지 돌려준다. 끝나지 않은 트랜잭션이 있으면 먼저 놓는다(바꿔치기는 이미 commit 됐거나 되돌려졌다)."""

    raw.rollback()
    cur = raw.cursor()
    cur.execute("SELECT pg_backend_pid(), pg_advisory_unlock(%s)", (LOCK_KEY,))
    now_pid, unlocked = cur.fetchone()
    raw.commit()
    return now_pid == pid and bool(unlocked)


def load(cur, table: str, paths: list[str], dongs: dict[str, str], prefixes: set[str]) -> tuple[int, int, int, int]:
    """파일들을 geo.{table}_next 에 COPY 한다. 돌려주는 값: (넣은 줄, 고유번호나 식별자가 없거나 잘못된 줄 - 넣지 않음, 지목을 못 읽은 땅 - 넣음,
    도형이 없거나 비어서 뺀 줄 - 넣지 않음. 품질 검사에는 아직 넣지 않았다 - 실측 뒤 정한다)."""

    import numpy as np
    import pyogrio
    import shapely
    from pyproj import CRS, Transformer

    cols = COLUMNS[table]
    wanted = list(dict.fromkeys(c for c in (cols["key"], cols["pnu"], cols["code"], cols["name"], cols["jimok"]) if c))
    to_ll = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
    rows = missing_keys = unknown_jimok = skipped_geometry = 0
    for path in paths:
        info = pyogrio.read_info(path)
        source = CRS.from_user_input(info["crs"])
        to_tm = None if source.to_epsg() == 5186 else Transformer.from_crs(source, "EPSG:5186", always_xy=True)
        total, skip = info["features"], 0
        while skip < total:
            meta, _, wkb, fd = pyogrio.raw.read(path, columns=wanted, skip_features=skip, max_features=CHUNK, encoding="cp949")
            skip += CHUNK
            field = dict(zip(meta["fields"], fd))
            pnu_raw = [(v or "").strip() if isinstance(v, str) else "" for v in field[cols["pnu"]]]
            key_raw = [v.strip() if isinstance(v, str) else "" for v in field[cols["key"]]]
            # 고유번호가 19자리 숫자가 아니거나 식별자가 빈 줄은 넣지 않고 센다(땅은 식별자가 곧 고유번호다)
            keep = np.array([is_pnu(p) and is_feature_key(k) for p, k in zip(pnu_raw, key_raw)], dtype=bool)
            missing_keys += int((~keep).sum())
            jimok_all = [jimok_of(v) for v in field[cols["jimok"]]] if cols["jimok"] else None
            if jimok_all is not None:
                keep &= np.array([keep_parcel(j) for j in jimok_all], dtype=bool)
            for code, name in zip(field[cols["code"]][keep], field[cols["name"]][keep]):
                if isinstance(code, str) and isinstance(name, str) and code.strip() and name.strip():
                    dongs.setdefault(code.strip(), " ".join(name.split()))
            g = shapely.from_wkb(wkb[keep])
            if to_tm is not None:
                g = shapely.transform(g, lambda xy: np.column_stack(to_tm.transform(xy[:, 0], xy[:, 1])))
            bad = ~shapely.is_valid(g)
            if bad.any():
                g[bad] = shapely.buffer(g[bad], 0)
            c = shapely.centroid(g)
            rep = np.where(shapely.contains(g, c), c, shapely.point_on_surface(g))
            rx, ry = shapely.get_x(rep), shapely.get_y(rep)
            lo, la = to_ll.transform(rx, ry)
            hexes = shapely.to_wkb(shapely.set_srid(g, 5186), hex=True, include_srid=True)
            pnus = [v for v, k in zip(pnu_raw, keep) if k]
            keys = [v for v, k in zip(key_raw, keep) if k]
            jimoks = [j for j, k in zip(jimok_all, keep) if k] if jimok_all is not None else None
            if jimoks is not None:
                unknown_jimok += sum(1 for j in jimoks if j is None)
            prefixes.update(pnu[:10] for pnu in pnus)
            names = "feature_key, pnu, la, lo, rx, ry, geom" + (", jimok" if jimoks is not None else "")
            with cur.copy(f"COPY geo.{table}_next ({names}) FROM STDIN") as copy:
                for k in range(len(pnus)):
                    if hexes[k] is not None and not shapely.is_empty(g[k]):
                        row = (keys[k], pnus[k], float(la[k]), float(lo[k]), float(rx[k]), float(ry[k]), hexes[k])
                        copy.write_row(row + ((jimoks[k],) if jimoks is not None else ()))
                        rows += 1
                    else:
                        skipped_geometry += 1
    return rows, missing_keys, unknown_jimok, skipped_geometry


def _swap(raw, counts: dict[str, int], dongs: dict[str, str], files: dict[str, list[str]]) -> bool:
    """바꿔치기만 짧은 트랜잭션. 잠금 시간 초과만 되돌려 원래 표를 그대로 두고 다시 해 본다 - 그 밖의 오류(데이터 오류 · 버그)는 되돌리고 그대로 올린다."""

    from psycopg.errors import LockNotAvailable

    for attempt in range(1, SWAP_TRIES + 1):
        cur = raw.cursor()
        try:
            cur.execute(f"SET LOCAL lock_timeout = '{SWAP_LOCK_TIMEOUT}'")
            for table in ("building", "parcel"):
                for statement in swap_statements(table):
                    cur.execute(statement)
            cur.execute("TRUNCATE geo.legal_dong")
            with cur.copy("COPY geo.legal_dong (code, name) FROM STDIN") as copy:
                for code, name in sorted(dongs.items()):
                    copy.write_row((code, name))
            cur.execute(
                "INSERT INTO geo.load_run (building_rows, parcel_rows, building_base_date, parcel_base_date) VALUES (%s, %s, %s, %s)",
                (counts["building"], counts["parcel"], base_date(files["building"]), base_date(files["parcel"])),
            )
            raw.commit()
            return True
        except LockNotAvailable as error:   # 읽는 쪽이 표를 쥐고 있다 - 되돌리고 다시
            raw.rollback()
            print(f"바꿔치기 {attempt}번째 실패: {type(error).__name__}", file=sys.stderr)
            if attempt < SWAP_TRIES:
                time.sleep(10)
        except Exception:
            raw.rollback()
            raise
    return False


def _drop_next(raw) -> None:
    """거부했거나 도중에 죽은 적재가 만들다 만 새 표를 지운다 - 표가 수 GB 라 남겨 두면 디스크가 모자란 서버에서 다음 적재가 못 돈다."""

    raw.rollback()   # 실패 도중이면 트랜잭션이 깨져 있을 수 있다
    cur = raw.cursor()
    for table in ("building", "parcel"):
        cur.execute(f"DROP TABLE IF EXISTS geo.{table}_next")
    raw.commit()
    print("만들다 만 geo.building_next · geo.parcel_next 를 지웠다", flush=True)


def _remove_unnamed(raw, missing: set[str], counts: dict[str, int]) -> dict[str, int]:
    """법정동 이름이 어디에도 없는 코드의 줄을 두 새 표에서 지운다(counts 를 줄이고 표마다 뺀 줄 수를 돌려준다). 코드 값은 찍지 않는다 - 개수만."""

    removed: dict[str, int] = {}
    cur = raw.cursor()
    for table in ("building", "parcel"):
        cur.execute(f"DELETE FROM geo.{table}_next WHERE left(pnu, 10) = ANY(%s)", (sorted(missing),))
        removed[table] = cur.rowcount
        counts[table] -= removed[table]
        cur.execute(f"ANALYZE geo.{table}_next")
    raw.commit()
    for table, count in removed.items():
        print(f"{table}: 법정동 이름 없는 코드 {len(missing):,}개 · 뺀 줄 {count:,}", flush=True)
    return removed


def _file_problems(files: dict[str, list[str]]) -> list[str]:
    """파일마다 좌표계와 내용 지문을 읽는다. 열리지 않는 파일은 역추적 대신 구조 문제로 센다."""

    problems: list[str] = []
    digests: dict[str, dict[str, str]] = {table: {} for table in files}
    for table, paths in files.items():
        for path in paths:
            name = Path(path).name
            try:
                if problem := source_crs_problem(path):
                    problems.append(problem)
                digests[table][name] = file_digest(path)
            except UNREADABLE as error:
                problems.append(f"{name}: unreadable ({type(error).__name__})")
    for table, by_name in digests.items():
        # 이름이 같은 두 파일은 manifest 가 이미 'duplicated file' 로 잡는다 - 여기서는 이름이 다르고 내용이 같은 것을 잡는다
        problems += [f"{table}: {problem}" for problem in content_duplicate_problems(by_name)]
    return problems


def run(buildings: Path, parcels: Path, *, connect: Callable[[], object], accept_row_count_change: bool) -> int:
    try:
        files = {"building": discover(buildings), "parcel": discover(parcels)}
    except UnreadableInput as problem:
        print(problem, file=sys.stderr)
        return 3
    if not files["building"] or not files["parcel"]:
        print("건물 · 땅 파일이 둘 다 있어야 한다", file=sys.stderr)
        return 2
    structural = [f"{t}: {p}" for t in files for p in manifest_problems(files[t], DATASET_OF[t])]
    if not structural:   # 이름 검사가 먼저 - 엉뚱한 파일 목록이면 열어 보지도 않는다
        structural += _file_problems(files)
    if structural:
        print("\n".join(structural), file=sys.stderr)
        return 3
    started = time.perf_counter()
    dongs: dict[str, str] = {}
    prefixes: set[str] = set()   # 넣은 고유번호의 앞 10자리(법정동코드) - 이름이 없는 코드의 줄은 두 표를 다 읽은 뒤 뺀다
    counts: dict[str, int] = {}
    removed: dict[str, int] = {}
    try:
        with exclusive_load(connect) as (raw, _pid):
            try:   # 잠금을 쥔 채로 - 어떤 이유로 죽든(거부가 아닌 예외도) 수 GB 짜리 새 표를 남기지 않는다. 원래 예외는 그대로 올린다
                for table in ("building", "parcel"):
                    cur = raw.cursor()
                    cur.execute(f"DROP TABLE IF EXISTS geo.{table}_next")
                    cur.execute(f"CREATE TABLE geo.{table}_next (LIKE geo.{table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)")
                    rows, missing_keys, unknown_jimok, skipped_geometry = load(cur, table, files[table], dongs, prefixes)
                    counts[table] = rows
                    cur.execute(f"ALTER TABLE geo.{table}_next ADD CONSTRAINT {table}_next_pkey PRIMARY KEY (id)")
                    cur.execute(f"CREATE INDEX {table}_next_geom_gix ON geo.{table}_next USING gist (geom)")
                    cur.execute(f"CREATE INDEX {table}_next_pnu_ix ON geo.{table}_next (pnu)")
                    cur.execute(f"ANALYZE geo.{table}_next")
                    cur.execute(f"SELECT count(DISTINCT feature_key) FROM geo.{table}_next")
                    distinct = cur.fetchone()[0]
                    raw.commit()   # 표마다 확정 - 같은 연결이라 잠금은 그대로다. 바꿔치기 앞까지 실패해도 지금 표는 그대로다
                    structural += quality_problems(table, rows, distinct, missing_keys=missing_keys, unknown_jimok=unknown_jimok)
                    print(f"{table}: 새 {rows:,}줄 · 고유 {distinct:,} · 식별자 빈 줄 {missing_keys:,} · 지목 못 읽음 {unknown_jimok:,} · 도형 빠짐 {skipped_geometry:,} · {time.perf_counter() - started:.0f}s", flush=True)
                if missing := prefixes - dongs.keys():
                    removed = _remove_unnamed(raw, missing, counts)
                    prefixes -= missing
                if unnamed := [p for table in counts for p in unnamed_dong_problems(table, counts[table], removed.get(table, 0))]:
                    print("\n".join(unnamed), file=sys.stderr)   # 4 - 이름 없는 코드의 줄이 한도를 넘었다(예전에는 하나라도 있으면 4)
                    _drop_next(raw)
                    return 4
                row_counts = [p for table in counts for p in row_count_problems(table, counts[table])]   # 뺀 뒤의 줄 수로
                if structural:
                    print("\n".join(structural), file=sys.stderr)
                    _drop_next(raw)
                    return 3
                if row_counts and not accept_row_count_change:
                    print("\n".join(row_counts) + "\n판이 정말 커지거나 줄었으면 --accept-row-count-change", file=sys.stderr)
                    _drop_next(raw)
                    return 8
                if not _swap(raw, counts, dongs, files):
                    _drop_next(raw)
                    return 6
            except BaseException:
                try:
                    _drop_next(raw)
                except Exception as cleanup_error:   # 지우다 또 실패해도 원래 오류를 가리지 않는다
                    print(f"만들다 만 새 표를 지우지 못했다: {type(cleanup_error).__name__}", file=sys.stderr)
                raise
    except LoadBusy:
        print("다른 적재가 돌고 있다", file=sys.stderr)
        return 5
    except LockLost:
        print("적재 연결이 바뀌었거나 잠금을 풀지 못했다 - pg_locks 를 확인할 것", file=sys.stderr)
        return 7
    print(f"바꿔치기 끝 · 법정동 {len(dongs):,} · {time.perf_counter() - started:.0f}s", flush=True)
    return 0


def main() -> int:
    from app.db.session import get_engine

    parser = argparse.ArgumentParser()
    parser.add_argument("--buildings", type=Path, required=True)
    parser.add_argument("--parcels", type=Path, required=True)
    parser.add_argument("--accept-row-count-change", action="store_true", help="행 수 범위만 받아들인다 - 구조 검사는 넘기지 못한다")
    args = parser.parse_args()
    # 엔진 풀에서 DBAPI 연결 하나를 빌려 끝까지 쓴다(raw_connection) - commit 사이에 다른 연결로 바뀌지 않는다
    return run(args.buildings, args.parcels, connect=get_engine().raw_connection, accept_row_count_change=args.accept_row_count_change)


if __name__ == "__main__":
    raise SystemExit(main())
