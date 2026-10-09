import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest
from psycopg.errors import LockNotAvailable

from app.services.geo_reference import EXPECTED_REGION_CODES
from scripts.geo_load import LockLost, _swap, base_date, discover, exclusive_load, file_digest, run


def test_extracted_folders_win_over_their_zip_and_lone_zips_are_read_inside(tmp_path: Path) -> None:
    (tmp_path / "AL_D010_11_20260909").mkdir()
    for name in ("AL_D010_11_20260909.shp", "AL_D010_11_20260909(2).shp"):
        (tmp_path / "AL_D010_11_20260909" / name).write_bytes(name.encode())
    for code in ("11", "26"):
        with zipfile.ZipFile(tmp_path / f"AL_D010_{code}_20260909.zip", "w") as zf:
            zf.writestr(f"AL_D010_{code}_20260909.shp", code.encode())
    found = discover(tmp_path)
    assert [Path(p).name for p in found if not p.startswith("/vsizip/")] == ["AL_D010_11_20260909(2).shp", "AL_D010_11_20260909.shp"]
    assert [p for p in found if p.startswith("/vsizip/")] == [f"/vsizip/{(tmp_path / 'AL_D010_26_20260909.zip').as_posix()}/AL_D010_26_20260909.shp"]


def test_the_digest_reads_the_shp_bytes_from_a_folder_or_inside_a_zip(tmp_path: Path) -> None:
    (tmp_path / "a.shp").write_bytes(b"same")
    with zipfile.ZipFile(tmp_path / "b.zip", "w") as zf:
        zf.writestr("b.shp", b"same")
    assert file_digest(str(tmp_path / "a.shp")) == file_digest(f"/vsizip/{(tmp_path / 'b.zip').as_posix()}/b.shp")


def test_the_base_date_is_the_latest_date_in_the_file_names() -> None:
    assert base_date(["/x/AL_D002_11_20260908.shp", "/vsizip//x/AL_D002_26_20260810.zip/AL_D002_26_20260810.shp"]) == "20260908"
    assert base_date(["/x/readme.shp"]) is None


def test_run_refuses_a_bad_file_set_before_connecting_even_with_the_row_count_option(tmp_path: Path) -> None:
    def no_db():
        raise AssertionError("connected")

    buildings, parcels = tmp_path / "buildings", tmp_path / "parcels"
    buildings.mkdir()
    parcels.mkdir()
    assert run(buildings, parcels, connect=no_db, accept_row_count_change=True) == 2   # 파일 없음
    (buildings / "AL_D010_11_20260909.shp").write_bytes(b"x")
    (parcels / "AL_D002_11_20260908.shp").write_bytes(b"x")
    # 시도 15개가 빠진 판 - 이름 검사가 먼저라 파일을 열거나 DB 에 붙지 않고, 행 수 옵션으로도 넘기지 못한다
    assert run(buildings, parcels, connect=no_db, accept_row_count_change=True) == 3


def test_shp_files_are_found_whatever_the_case_of_the_extension(tmp_path: Path) -> None:
    (tmp_path / "AL_D010_11_20260909.SHP").write_bytes(b"x")
    assert [Path(p).name for p in discover(tmp_path)] == ["AL_D010_11_20260909.SHP"]


def test_run_reports_a_broken_zip_as_a_structural_problem_before_connecting(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def no_db():
        raise AssertionError("connected")

    buildings, parcels = tmp_path / "buildings", tmp_path / "parcels"
    buildings.mkdir()
    parcels.mkdir()
    for code in sorted(EXPECTED_REGION_CODES):   # 이름은 시도 16개가 다 맞다 - 하나만 zip 인데 zip 이 아니다
        (parcels / f"AL_D002_{code}_20260908.shp").write_bytes(b"x")
        if code != "11":
            (buildings / f"AL_D010_{code}_20260909.shp").write_bytes(b"x")
    (buildings / "AL_D010_11_20260909.zip").write_bytes(b"this is not a zip")
    assert run(buildings, parcels, connect=no_db, accept_row_count_change=True) == 3
    assert "AL_D010_11_20260909.zip: unreadable (BadZipFile)" in capsys.readouterr().err


def test_run_reports_a_zip_member_with_a_corrupted_deflate_body_as_unreadable_before_connecting(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_db():
        raise AssertionError("connected")

    monkeypatch.setattr("scripts.geo_load.source_crs_problem", lambda _path: None)   # 좌표계 검사는 건너뛰어 내용 지문(zip 해제)에서 깨짐이 드러나게 한다
    buildings, parcels = tmp_path / "buildings", tmp_path / "parcels"
    buildings.mkdir()
    parcels.mkdir()
    for code in sorted(EXPECTED_REGION_CODES):   # 이름은 시도 16개가 다 맞고 내용은 서로 다르다 - 건물 11 하나만 압축 본문이 깨졌다
        (parcels / f"AL_D002_{code}_20260908.shp").write_bytes(f"parcel {code}".encode())
        member = f"AL_D010_{code}_20260909.shp"
        with zipfile.ZipFile(buildings / f"AL_D010_{code}_20260909.zip", "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(member, (f"building {code} " * 500).encode())
    broken = buildings / "AL_D010_11_20260909.zip"
    raw = bytearray(broken.read_bytes())
    start = raw.index(b"AL_D010_11_20260909.shp") + len("AL_D010_11_20260909.shp")   # 로컬 머리글 다음이 압축 본문이다
    raw[start + 8] ^= 0xFF
    broken.write_bytes(bytes(raw))
    assert run(buildings, parcels, connect=no_db, accept_row_count_change=True) == 3
    assert "AL_D010_11_20260909.shp: unreadable (" in capsys.readouterr().err


class FakeConnection:
    """exclusive_load 가 쓰는 연결의 대역 - fetchone 이 미리 정한 답을 차례로 돌려준다(잠금 · 잠금 풀기)."""

    def __init__(self, *answers: tuple[int, bool]) -> None:
        self.answers, self.closed = list(answers), False

    def cursor(self):
        return self

    def execute(self, *args) -> None:
        pass

    def fetchone(self) -> tuple[int, bool]:
        return self.answers.pop(0)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("unlock", [(2, True), (1, False)], ids=["other-connection", "not-unlocked"])
def test_a_changed_connection_or_a_failed_unlock_ends_in_lock_lost(unlock: tuple[int, bool]) -> None:
    conn = FakeConnection((1, True), unlock)
    with pytest.raises(LockLost):
        with exclusive_load(lambda: conn):
            pass
    assert conn.closed


def test_a_failing_load_keeps_its_own_error_when_the_unlock_fails_too(capsys: pytest.CaptureFixture[str]) -> None:
    conn = FakeConnection((1, True), (2, False))
    with pytest.raises(ValueError, match="load failed"):
        with exclusive_load(lambda: conn):
            raise ValueError("load failed")
    assert conn.closed and "pg_locks" in capsys.readouterr().err


def write_month_names(tmp_path: Path) -> tuple[Path, Path]:
    """이름만 시도 16개가 다 맞는 판 - 파일을 열지 않는 시험용(_file_problems 와 load 는 시험이 바꿔 낀다)."""

    buildings, parcels = tmp_path / "buildings", tmp_path / "parcels"
    buildings.mkdir()
    parcels.mkdir()
    for code in sorted(EXPECTED_REGION_CODES):
        (buildings / f"AL_D010_{code}_20260909.shp").write_bytes(b"x")
        (parcels / f"AL_D002_{code}_20260908.shp").write_bytes(b"x")
    return buildings, parcels


def test_a_building_table_that_fails_the_quality_check_stops_before_the_parcels_are_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_load(_cur, table, _paths, _dongs, _prefixes):
        calls.append(table)
        if table == "parcel":
            pytest.fail("땅 파일을 읽었다")   # 실제로는 약 2시간
        return 16, 1, 0, 0   # 식별자 빈 줄 1/17 - 0.1% 를 넘는다

    monkeypatch.setattr("scripts.geo_load._file_problems", lambda _files: [])
    monkeypatch.setattr("scripts.geo_load.load", fake_load)
    conn = FakeConnection((1, True), (16,), (1, True))   # 잠금 · 건물 고유 식별자 수 · 잠금 풀기
    assert run(*write_month_names(tmp_path), connect=lambda: conn, accept_row_count_change=True) == 3
    out, err = capsys.readouterr()
    assert calls == ["building"] and "building: rows without a feature key" in err
    assert "만들다 만 geo.building_next · geo.parcel_next 를 지웠다" in out and conn.closed and not conn.answers


def test_exit_4_also_prints_the_quality_problems_found_so_far(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_load(_cur, table, _paths, dongs, prefixes):
        prefixes.update({"1111010100", "1111010200"})
        dongs.setdefault("1111010100", "시험시 시험동")   # 1111010200 은 어디에도 이름이 없다
        return (16, 0, 0, 0) if table == "building" else (16, 0, 1, 0)   # 땅은 지목 못 읽음 1/16 - 1% 를 넘는다

    monkeypatch.setattr("scripts.geo_load._file_problems", lambda _files: [])
    monkeypatch.setattr("scripts.geo_load.load", fake_load)
    conn = FakeConnection((1, True), (16,), (16,), (1, True))
    conn.rowcount = 1   # 표마다 이름 없는 코드의 줄 1개를 뺀다 - 1/16 이 1% 를 넘는다
    assert run(*write_month_names(tmp_path), connect=lambda: conn, accept_row_count_change=True) == 4
    err = capsys.readouterr().err
    assert "parcel: unknown land category" in err and "rows with an unnamed legal-dong code" in err


class FakeSwapConnection:
    """_swap 이 쓰는 연결의 대역 - 문장을 실행할 때마다 errors 를 하나씩 던지고, 다 던진 뒤에는 성공한다."""

    def __init__(self, *errors: Exception) -> None:
        self.errors, self.rollbacks, self.commits = list(errors), 0, 0

    def cursor(self):
        return self

    def execute(self, *args) -> None:
        if self.errors:
            raise self.errors.pop(0)

    @contextmanager
    def copy(self, *args):
        yield self

    def write_row(self, row) -> None:
        pass

    def rollback(self) -> None:
        self.rollbacks += 1

    def commit(self) -> None:
        self.commits += 1


SWAP_ARGS = ({"building": 1, "parcel": 1}, {}, {"building": [], "parcel": []})


def test_the_swap_retries_only_a_lock_timeout_and_gives_up_after_three(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.geo_load.time.sleep", lambda _seconds: None)
    retried = FakeSwapConnection(LockNotAvailable("busy"))
    assert _swap(retried, *SWAP_ARGS) is True and (retried.rollbacks, retried.commits) == (1, 1)
    stuck = FakeSwapConnection(*[LockNotAvailable("busy")] * 3)
    assert _swap(stuck, *SWAP_ARGS) is False and (stuck.rollbacks, stuck.commits) == (3, 0)


def test_the_swap_rolls_back_and_raises_any_other_error_without_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("scripts.geo_load.time.sleep", lambda _seconds: pytest.fail("retried a non lock-timeout error"))
    broken = FakeSwapConnection(RuntimeError("data error"), RuntimeError("never reached"))
    with pytest.raises(RuntimeError, match="data error"):
        _swap(broken, *SWAP_ARGS)
    assert (broken.rollbacks, broken.commits) == (1, 0)
