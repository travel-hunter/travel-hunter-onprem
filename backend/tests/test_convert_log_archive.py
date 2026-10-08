"""scripts/convert_log_archive.py — 옛 달별 보관본을 날짜별 배치로 한 번 옮긴다.

계획: docs/superpowers/plans/2026-10-08-log-daily-archive.md
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "convert_log_archive.py"


def _load():
    spec = importlib.util.spec_from_file_location("convert_log_archive_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


convert = _load()
pull_logs = convert.pull_logs
trace = convert.trace


def line(ts: str, path: str, rid: str = "r1") -> bytes:
    return (json.dumps({"ts": ts, "kind": "access", "request_id": rid, "method": "GET", "path": path,
                        "status": 200, "duration_ms": 1}) + "\n").encode()


def legacy_archive(tmp_path: Path) -> Path:
    """배포 직후의 보관 폴더: 9월은 조각 둘(늦은 줄이 p02), 10월은 평문(확정 크기 뒤에 꼬리), 새 코드가 만든 오늘 파일."""
    folder = tmp_path / "dev"
    folder.mkdir()
    (folder / "backend-2026-09.p01-aaaaaaaaaaaa.log.gz").write_bytes(
        gzip.compress(line("2026-09-28T10:00:00+09:00", "/sep28") + line("2026-09-30T23:58:00+09:00", "/sep30a")))
    (folder / "backend-2026-09.p02-bbbbbbbbbbbb.log.gz").write_bytes(gzip.compress(line("2026-09-30T23:59:00+09:00", "/sep30b")))
    october = (line("2026-10-01T09:00:00+09:00", "/oct1")
               + line("2026-10-08T09:00:00+09:00", "/oct8-before", "old-code") + b"uvicorn banner\n")
    (folder / "backend-2026-10.log").write_bytes(october + line("2026-10-08T09:01:00+09:00", "/unsaved-tail"))
    (folder / ".state.json").write_text(json.dumps({"_files": {"backend-2026-10.log": len(october)}}), "utf-8")
    (folder / "2026-10").mkdir()
    (folder / "2026-10" / "backend-2026-10-08.log").write_bytes(line("2026-10-08T10:00:00+09:00", "/oct8-after", "new-code"))
    (folder / "notes.txt").write_text("mine", "utf-8")
    return folder


def chunk(folder: Path, day: str) -> str:
    [path] = (folder / day[:7]).glob(f"backend-{day}.p00-*.log.gz")
    return gzip.decompress(path.read_bytes()).decode()


def trace_paths(folder: Path) -> list[str]:
    return [r["path"] for r in trace.read_local_file("backend", str(folder), 1024 * 1024)]


ALL = ["/sep28", "/sep30a", "/sep30b", "/oct1", "/oct8-before", "/oct8-after"]


def tree(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*"))


def test_monthly_files_become_day_chunks_and_move_aside(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    assert "/sep28" in chunk(folder, "2026-09-28")
    sep30 = chunk(folder, "2026-09-30")
    assert sep30.index("/sep30a") < sep30.index("/sep30b"), "조각 번호순 - 늦은 줄이 뒤에"
    oct8 = chunk(folder, "2026-10-08")
    assert "uvicorn banner" in oct8, "시각 없는 줄은 앞 줄의 날로 (그 달 1일이 아니라)"
    assert "/oct8-before" in oct8 and "/unsaved-tail" not in oct8, "확정 크기 뒤 꼬리는 넣지 않는다"
    assert sorted(p.name for p in (folder / ".legacy-monthly").iterdir()) == [
        "backend-2026-09.p01-aaaaaaaaaaaa.log.gz", "backend-2026-09.p02-bbbbbbbbbbbb.log.gz", "backend-2026-10.log"]
    assert not list(folder.glob("backend-*")) and (folder / "notes.txt").exists()


def test_trace_reads_converted_and_live_lines_once_in_order(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    assert trace_paths(folder) == ALL


def test_rerunning_the_conversion_changes_nothing(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    before = tree(folder)
    convert.convert(folder)
    assert tree(folder) == before and convert.verify(folder)[1]


def test_a_conversion_stopped_before_moving_finishes_without_duplicates(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    legacy = folder / ".legacy-monthly"
    for name in ("backend-2026-09.p02-bbbbbbbbbbbb.log.gz", "backend-2026-10.log"):
        (legacy / name).replace(folder / name)  # 조각은 썼고 원본 일부를 옮기기 전에 멈춘 상태
    convert.convert(folder)
    assert trace_paths(folder) == ALL and convert.verify(folder)[1]


def test_a_different_p00_for_the_same_day_stops_the_conversion(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / "2026-10" / "backend-2026-10-08.p00-000000000000.log.gz").write_bytes(gzip.compress(b"other\n"))
    with pytest.raises(convert.ConvertError, match="다른 내용"):
        convert.convert(folder)
    assert (folder / "backend-2026-10.log").exists(), "멈춘 달의 원본은 옮기지 않는다"


def test_a_stopped_month_writes_no_day_so_trace_has_no_duplicates(tmp_path):
    """10-08 에서 멈추면 10-01 의 p00 도 쓰지 않는다. 원본이 맨 위에 남아 있으니 쓴 날은 trace 에 두 번 보인다."""
    folder = legacy_archive(tmp_path)
    (folder / "2026-10" / "backend-2026-10-08.p00-000000000000.log.gz").write_bytes(gzip.compress(b"other\n"))
    with pytest.raises(convert.ConvertError):
        convert.convert(folder)
    assert not list((folder / "2026-10").glob("backend-2026-10-01.*"))
    paths = trace_paths(folder)
    assert "/oct1" in paths and len(paths) == len(set(paths))


def test_a_past_month_left_both_plain_and_compressed_is_converted_once(tmp_path):
    folder = legacy_archive(tmp_path)
    august = line("2026-08-31T10:00:00+09:00", "/aug")
    digest = hashlib.sha256(august).hexdigest()[:12]
    (folder / f"backend-2026-08.p01-{digest}.log.gz").write_bytes(gzip.compress(august))
    (folder / "backend-2026-08.log").write_bytes(august)  # 옛 archive() 가 압축 뒤 원본 삭제 전에 멈춘 흔적
    convert.convert(folder)
    assert chunk(folder, "2026-08-31").count("/aug") == 1
    assert convert.verify(folder)[1] and not list(folder.glob("backend-*"))
    assert trace_paths(folder) == ["/aug"] + ALL
    assert convert.remove(folder) == 5


def test_a_broken_old_chunk_stops_the_conversion_cleanly(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / "backend-2026-09.p03-cccccccccccc.log.gz").write_bytes(b"not gzip")
    with pytest.raises(convert.ConvertError, match="풀지 못했다"):
        convert.convert(folder)
    assert not (folder / "2026-09").exists() and (folder / "backend-2026-09.p01-aaaaaaaaaaaa.log.gz").exists()


def test_conversion_waits_for_the_new_writer(tmp_path):
    folder = legacy_archive(tmp_path)
    shutil.rmtree(folder / "2026-10")
    with pytest.raises(convert.ConvertError, match="YYYY-MM"):
        convert.convert(folder)


def test_conversion_takes_the_archive_lock(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / ".lock").touch()
    with pytest.raises(pull_logs.PullError, match="잠금"):
        convert.convert(folder)
    assert not (folder / ".legacy-monthly").exists()


def test_verify_flags_a_damaged_chunk_and_remove_refuses(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    [damaged] = (folder / "2026-09").glob("backend-2026-09-28.p00-*.log.gz")
    damaged.write_bytes(gzip.compress(b"damaged\n"))
    rows, ok = convert.verify(folder)
    assert not ok and any("2026-09-28" in row and row.endswith("DIFF") for row in rows)
    with pytest.raises(convert.ConvertError):
        convert.remove(folder)
    assert len(list((folder / ".legacy-monthly").iterdir())) == 3


def test_verify_catches_bytes_that_are_not_whole_lines(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / "backend-2026-09.p03-cccccccccccc.log.gz").write_bytes(gzip.compress(b"no newline at the end"))
    convert.convert(folder)
    rows, ok = convert.verify(folder)
    assert not ok and any("2026-09 합계" in row and row.endswith("DIFF") for row in rows)


def test_remove_refuses_while_originals_are_unconverted(tmp_path):
    folder = legacy_archive(tmp_path)
    with pytest.raises(convert.ConvertError):
        convert.remove(folder)
    assert (folder / "backend-2026-10.log").exists()


def test_remove_deletes_only_the_verified_originals(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    assert convert.remove(folder) == 3
    assert not (folder / ".legacy-monthly").exists()
    assert (folder / "notes.txt").exists() and (folder / ".state.json").exists()
    assert trace_paths(folder) == ALL


def test_the_writer_numbers_its_chunks_after_the_converted_one(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    live = "2026-10/backend-2026-10-08.log"
    committed = {live: (folder / live).stat().st_size}
    pull_logs.archive(folder, "2026-10-09", 12, committed, lambda: None)  # 10-08 이 닫혔다
    parts = sorted(trace.ARCHIVE_NAME.fullmatch(p.name)["part"] for p in (folder / "2026-10").glob("backend-2026-10-08.*"))
    assert parts == ["00", "01"]
    assert trace_paths(folder) == ALL


def test_cli_prints_counts_not_log_content(tmp_path, monkeypatch, capsys):
    legacy_archive(tmp_path)
    monkeypatch.setattr("sys.argv", ["convert_log_archive.py", "convert", "--dest", str(tmp_path), "--label", "dev"])
    assert convert.main() == 0
    out = capsys.readouterr().out
    assert "2026-10-08" in out and "검증: 모두 맞음" in out
    assert "/oct8" not in out and "old-code" not in out and "banner" not in out


def test_a_month_over_the_memory_limit_stops_before_writing(tmp_path, monkeypatch):
    folder = legacy_archive(tmp_path)
    monkeypatch.setattr(convert, "MAX_MONTH_BYTES", 10)
    with pytest.raises(convert.ConvertError, match="backend 2026-09"):
        convert.convert(folder)
    assert not (folder / "2026-09").exists() and not (folder / ".legacy-monthly").exists()


def test_a_corrupted_deflate_body_stops_the_conversion_cleanly(tmp_path):
    folder = legacy_archive(tmp_path)
    packed = bytearray(gzip.compress(line("2026-09-29T10:00:00+09:00", "/sep29")))
    packed[10] ^= 0xFF  # 머리(10바이트) 바로 뒤 deflate 블록 머리 - zlib.error 가 난다
    (folder / "backend-2026-09.p03-cccccccccccc.log.gz").write_bytes(bytes(packed))
    with pytest.raises(convert.ConvertError, match="풀지 못했다"):
        convert.convert(folder)
    assert not (folder / "2026-09").exists() and not (folder / ".legacy-monthly").exists()


def test_cli_exit_codes_for_a_difference_and_an_error(tmp_path, monkeypatch, capsys):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    [damaged] = (folder / "2026-09").glob("backend-2026-09-28.p00-*.log.gz")
    damaged.write_bytes(gzip.compress(b"damaged\n"))
    monkeypatch.setattr("sys.argv", ["convert_log_archive.py", "verify", "--dest", str(tmp_path), "--label", "dev"])
    assert convert.main() == 1
    (folder / ".state.json").write_text("{broken", "utf-8")
    assert convert.main() == 3
    assert ".state.json" in capsys.readouterr().err
