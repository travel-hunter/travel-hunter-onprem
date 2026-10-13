#!/usr/bin/env python3
"""옛 달별 보관본을 날짜별 배치로 한 번 옮긴다 (일회성 - 다 옮기고 지운 뒤에는 이 파일도 지운다).

계획: docs/superpowers/plans/2026-10-08-log-daily-archive.md

  python3 scripts/convert_log_archive.py convert --dest /mnt/d/travel-hunter-logs --label dev   # 옮기고 검증표
  python3 scripts/convert_log_archive.py verify  --dest /mnt/d/travel-hunter-logs --label dev   # 검증표만 (읽기만)
  python3 scripts/convert_log_archive.py remove  --dest /mnt/d/travel-hunter-logs --label dev   # 다 맞을 때만 원본 삭제

- 맨 위의 <stem>-YYYY-MM[.pNN-해시].log[.gz] 를 줄 시각(KST)의 날로 나눠 YYYY-MM/<stem>-YYYY-MM-DD.p00-<해시>.log.gz 로 쓴다.
  p00 은 이 변환만 쓰는 번호다 - 그날의 새 기록(p01~, .log)보다 늘 먼저 읽힌다.
- 시각을 못 읽은 줄은 바로 앞 줄의 날로 간다(그 달의 첫 줄이면 1일).
- 평문 달 파일은 .state.json 의 확정 크기까지만 읽는다. 그 뒤는 저장 전에 멈춘 꼬리라 새 코드가 볼륨에서 다시 받았다.
- 같은 내용은 같은 이름이라 다시 돌려도 그대로다. 같은 날에 다른 내용의 p00 이 있으면 멈춘다.
- 원본은 .legacy-monthly/ 로 옮겨 둔다(trace --dir 가 두 번 읽지 않게). 지우는 것은 remove 뿐이다.
- pull_logs.py 와 같은 잠금을 잡는다. 그동안 logarchive 회차는 '잠금' 오류로 쉬고 다음 회차에 따라잡는다.
- 줄 내용은 출력하지 않는다. 날마다 줄 수·바이트·sha256 앞 12자만.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import re
import sys
import zlib
from contextlib import suppress
from pathlib import Path


def _load_pull_logs():
    spec = importlib.util.spec_from_file_location("pull_logs_script", Path(__file__).with_name("pull_logs.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


pull_logs = _load_pull_logs()
trace = pull_logs.trace
LEGACY_DIR = ".legacy-monthly"
MAX_MONTH_BYTES = 1024 * 1024 * 1024  # 한 (stem, 달)을 풀었을 때 - 넘으면 메모리에 올리기 전에 멈춘다
GZIP_ERRORS = (OSError, EOFError, zlib.error)


class ConvertError(RuntimeError):
    """변환을 멈췄다. 원본은 그대로다."""


def is_monthly(name: str) -> bool:
    match = trace.ARCHIVE_NAME.fullmatch(name)
    return bool(match) and len(match["period"]) == 7


def legacy_groups(folder: Path) -> dict[tuple[str, str], list[Path]]:
    """(stem, 달) → 옛 달별 파일, 읽는 순서대로. 맨 위와 .legacy-monthly/ 를 함께 본다 - 옮기다 멈춰도 같은 내용이 된다."""
    groups: dict[tuple[str, str], list] = {}
    for directory in (folder, folder / LEGACY_DIR):
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if is_monthly(path.name):
                match = trace.ARCHIVE_NAME.fullmatch(path.name)
                groups.setdefault((match["stem"], match["period"]), []).append((trace.archive_order(match), path))
    return {key: [path for _, path in sorted(items)] for key, items in sorted(groups.items())}


def committed_sizes(folder: Path) -> dict[str, int]:
    state_path = folder / ".state.json"
    try:
        return json.loads(state_path.read_text("utf-8")).get(pull_logs.FILES_KEY, {}) if state_path.exists() else {}
    except ValueError as error:
        raise ConvertError(f".state.json 을 읽지 못했다({type(error).__name__}) - 멈춘다") from None


def unreadable(path: Path, error: BaseException) -> ConvertError:
    return ConvertError(f"{path.name} 을 풀지 못했다({type(error).__name__}) - 멈춘다")


def unpacked_size(path: Path, committed: dict[str, int]) -> int:
    """풀었을 때의 바이트 - 메모리에 올리지 않고 센다. 평문은 확정 크기까지."""
    if not path.name.endswith(".gz"):
        size = path.stat().st_size
        return min(size, committed.get(path.name, size))
    try:
        with gzip.open(path, "rb") as handle:
            return sum(iter(lambda: len(handle.read(1024 * 1024)), 0))
    except GZIP_ERRORS as error:
        raise unreadable(path, error) from None


def split_days(paths: list[Path], month: str, committed: dict[str, int]) -> tuple[dict[str, bytes], int]:
    """(날 → 그날 줄들, 읽은 전체 바이트). 평문은 확정 크기까지만 - 기록이 없으면 통째로(지우는 것보다 낫다).

    같은 달의 조각과 해시가 같은 평문은 건너뛴다 - 압축은 됐는데 원본 삭제 전에 멈춘 흔적이다(옛 archive() 와 같은 규칙).
    """
    size = sum(unpacked_size(path, committed) for path in paths)
    if size > MAX_MONTH_BYTES:
        stem = trace.ARCHIVE_NAME.fullmatch(paths[0].name)["stem"]
        raise ConvertError(f"{stem} {month} 을 풀면 {size} 바이트 - 한도 {MAX_MONTH_BYTES} 를 넘어 멈춘다(이 달 원본은 그대로)")
    chunk_hashes = {trace.ARCHIVE_NAME.fullmatch(p.name)["hash"] for p in paths if p.name.endswith(".gz")}
    days: dict[str, list[bytes]] = {}
    day, total = f"{month}-01", 0
    for path in paths:
        if path.name.endswith(".gz"):
            try:
                with gzip.open(path, "rb") as handle:
                    data = handle.read()  # ponytail: 한 달을 메모리에 - MAX_MONTH_BYTES 로 막는다, 더 크면 줄 단위로 바꾼다
            except GZIP_ERRORS as error:
                raise unreadable(path, error) from None
        else:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest()[:12] in chunk_hashes:
                continue
            data = raw[:committed.get(path.name)]
        total += len(data)
        for line in re.findall(rb"[^\n]*\n", data):
            day = pull_logs.line_day(line, day)
            days.setdefault(day, []).append(line)
    return {d: b"".join(lines) for d, lines in sorted(days.items())}, total


def chunk_path(folder: Path, stem: str, day: str, digest: str) -> Path:
    return folder / day[:7] / f"{stem}-{day}.p00-{digest}.log.gz"


def convert(folder: Path) -> None:
    if not any(trace.MONTH_DIR.fullmatch(p.name) and p.is_dir() for p in folder.iterdir()):
        raise ConvertError("날짜별 폴더(YYYY-MM/)가 아직 없다 - 새 pull_logs.py 가 한 번 돈 뒤에 변환한다")
    with pull_logs.Lock(folder / ".lock"):
        committed = committed_sizes(folder)
        for (stem, month), paths in legacy_groups(folder).items():
            # 이 달의 모든 날을 먼저 확인한다 - 중간에 멈추면 이 달은 아무것도 쓰지 않는다(쓴 날만 trace 에 두 번 보이지 않게).
            targets = {}
            for day, data in split_days(paths, month, committed)[0].items():
                target = chunk_path(folder, stem, day, hashlib.sha256(data).hexdigest()[:12])
                others = [p.name for p in target.parent.glob(f"{stem}-{day}.p00-*.log.gz") if p != target]
                if others:
                    raise ConvertError(f"{day[:7]}/{others[0]} 가 이미 다른 내용이다 - 멈춘다(이 달 원본은 그대로)")
                targets[target] = data
            for target, data in targets.items():
                if not target.exists():
                    target.parent.mkdir(exist_ok=True)
                    temp = target.with_name(target.name + ".tmp")
                    with gzip.open(temp, "wb") as packed:
                        packed.write(data)
                    temp.replace(target)
            (folder / LEGACY_DIR).mkdir(exist_ok=True)
            for path in paths:  # 이 달을 다 쓴 뒤에 옮긴다
                if path.parent == folder:
                    path.replace(folder / LEGACY_DIR / path.name)


def verify(folder: Path) -> tuple[list[str], bool]:
    """원본에서 다시 나눈 날별 내용과 p00 조각을 바이트 단위로 맞춰 본다. 읽기만 한다."""
    committed = committed_sizes(folder)
    rows, ok = [], True
    for (stem, month), paths in legacy_groups(folder).items():
        days, total = split_days(paths, month, committed)
        month_lines = 0
        for day, data in days.items():
            digest = hashlib.sha256(data).hexdigest()[:12]
            try:
                same = gzip.decompress(chunk_path(folder, stem, day, digest).read_bytes()) == data
            except GZIP_ERRORS:  # 없거나 깨진 p00 은 '다름'이다 - 검증 결과지 오류가 아니다
                same = False
            ok = ok and same
            lines = data.count(b"\n")
            month_lines += lines
            rows.append(f"{stem:<12} {day}     lines={lines:<8} bytes={len(data):<10} sha={digest}  {'OK' if same else 'DIFF'}")
        whole = sum(map(len, days.values())) == total  # 줄로 나누다 흘린 바이트가 없다
        ok = ok and whole
        rows.append(f"{stem:<12} {month} 합계 lines={month_lines:<8} bytes={total:<10} {'OK' if whole else 'DIFF'}")
    return rows, ok


def remove(folder: Path) -> int:
    """검증이 다 맞고 맨 위에 옮기지 않은 원본이 없을 때만 .legacy-monthly/ 의 원본을 지운다. 지운 개수.

    .state.json 의 옛 키는 그대로 둔다 - 파일이 없으면 아무도 읽지 않는다. 상태 파일을 쓰는 프로그램을 늘리지 않는다.
    """
    with pull_logs.Lock(folder / ".lock"):
        _rows, ok = verify(folder)
        if not ok or any(is_monthly(p.name) for p in folder.iterdir()):
            raise ConvertError("검증이 다 맞지 않았거나 아직 옮기지 않은 원본이 있다 - 지우지 않는다 (verify 로 확인)")
        legacy = folder / LEGACY_DIR
        names = [p.name for p in legacy.iterdir() if is_monthly(p.name)] if legacy.is_dir() else []
        for name in names:
            (legacy / name).unlink()
        with suppress(OSError):
            legacy.rmdir()
        return len(names)


def main() -> int:
    parser = argparse.ArgumentParser(description="옛 달별 보관본을 날짜별로 한 번 옮긴다")
    parser.add_argument("command", choices=("convert", "verify", "remove"))
    parser.add_argument("--dest", default=os.environ.get("TRACE_LOCAL_DIR"), help="pull_logs.py 의 --dest")
    parser.add_argument("--label", required=True, help="보관 폴더 안의 이름 (개발서버: dev)")
    args = parser.parse_args()
    if not args.dest:
        parser.error("--dest 또는 TRACE_LOCAL_DIR 가 필요하다")
    folder = Path(args.dest) / args.label
    if not folder.is_dir():
        parser.error(f"보관 폴더가 없다: {folder}")
    try:
        if args.command == "remove":
            print(f"원본 {remove(folder)}개를 지웠다")
            return 0
        if args.command == "convert":
            convert(folder)
        rows, ok = verify(folder)
    except (ConvertError, pull_logs.PullError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 3
    print("\n".join(rows) if rows else "옛 달별 파일 없음")
    print("검증: 모두 맞음" if ok else "검증: 다른 곳이 있다 - remove 하지 말 것")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
