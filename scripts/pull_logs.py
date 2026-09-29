#!/usr/bin/env python3
"""볼륨 로그(단기, 회전·삭제)를 텍스트 파일로 빼서 오래 보관한다.

계획: docs/superpowers/plans/2026-09-28-pull-logs-to-local.md (rev4·rev5)

개발서버 안에서 cron 으로 (보관 위치는 그 PC 의 D: 드라이브 - Docker 볼륨 밖, WSL 밖):
  */5 * * * * cd ~/travel-hunter-onprem && python3 scripts/pull_logs.py --label dev --dest /mnt/d/travel-hunter-logs
다른 PC 에서 SSH 로 받아 올 수도 있다:
  python scripts/pull_logs.py --dev --dest D:/travel-hunter-logs

결과: <dest>/<label>/caddy-access-2026-09.log, backend-2026-09.log
      지난달은 조각으로 압축: backend-2026-08.p01-<해시>.log.gz (늦게 온 줄은 p02 …)
조회: scripts/trace --dir <dest>/<label> <문의코드>

- 파일 이름이 아니라 inode 로 추적한다. backend 회전은 .1 → .2 로 이름을 밀지만 inode 는 그대로다.
  가져올 때 같은 명령 안에서 inode 를 다시 확인한다 - 그 사이 회전됐으면 이번엔 건너뛴다.
- 받은 위치와 보관 파일의 확정 크기는 <dest>/<label>/.state.json 에 둔다. 확정 크기보다 긴 보관 파일은
  저장 전에 멈춘 흔적이라 시작할 때 잘라 되돌린다 - 다시 받아도 중복이 없다.
- 쓰는 중인 반쪽 줄은 받지 않는다(마지막 줄바꿈까지만).
- 줄의 시각(KST)으로 달을 나눈다. 지난달은 내용 해시 이름의 조각으로 압축한다(같은 내용이면 같은 이름이라
  압축 중에 멈췄다 다시 해도 중복이 없다). --keep-months 보다 오래된 달은 지운다.
- 서버에서 부르는 명령은 stat · tail · head 뿐이다. 파일 이름은 trace 와 같은 정규식을 통과한 것만 쓴다.
- 보관 형식이 계약이다(한 줄 한 JSON, 시간순). AWS(CloudWatch)로 옮기면 원격 읽기(remote_files · fetch)만 바꾼다.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat as statmod
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import NamedTuple


def _load_trace():
    # 'import trace' 는 표준 라이브러리 trace 와 이름이 겹친다. 경로로 읽는다.
    spec = importlib.util.spec_from_file_location("trace_script", Path(__file__).with_name("trace.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


trace = _load_trace()

STEMS = (trace.EDGE_STEM, trace.APP_STEM)
DEFAULT_MAX_MB = 64
DEFAULT_KEEP_MONTHS = 12
LOCK_STALE_SECONDS = 3600
MOVED = 4  # 가져오는 사이 회전돼 이름이 다른 파일을 가리킨다
ARCHIVE_FILE = re.compile(
    rf"^(?P<stem>{'|'.join(map(re.escape, STEMS))})-(?P<month>\d{{4}}-\d{{2}})"
    r"(?:\.p(?P<part>\d+)-(?P<hash>[0-9a-f]{12}))?\.log(?P<gz>\.gz)?$"
)
FILES_KEY = "_files"  # 보관 파일의 확정 크기


class PullError(RuntimeError):
    """서버를 읽지 못했다. '새 로그 없음'과 구분한다."""


def _run(container: str, script: str, env: dict[str, str], binary: bool = False):
    return subprocess.run(["docker", "exec", container, "sh", "-c", script], capture_output=True, env=env,
                          **({} if binary else {"encoding": "utf-8", "errors": "replace"}))


def remote_files(container: str, stem: str, env: dict[str, str]) -> list[tuple[str, int, str]]:
    """(inode, 크기, 이름) 을 오래된 것부터."""
    done = _run(container, f"cd {trace.LOG_DIR} && stat -c '%i %s %n' *", env)
    if done.returncode != 0:
        # 빈 디렉터리면 '*' 가 그대로 남아 stat 이 실패한다 - 그건 '파일 없음'이다.
        if "'*'" in (done.stderr or "") or "*: No such file" in (done.stderr or ""):
            return []
        raise PullError(f"{container}: {trace._failure(done)}")
    pattern = _name_pattern(stem)
    files = []
    for line in trace._lines(done.stdout):
        parts = line.strip().split(" ", 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() and pattern.fullmatch(parts[2]):
            files.append((parts[0], int(parts[1]), parts[2]))
    files.sort(key=lambda item: trace._rotation_order(item[2], stem))
    return files


def _name_pattern(stem: str) -> re.Pattern:
    # 이름에 셸 문자가 섞이면 받지 않는다(docker exec 모드는 이름이 sh -c 인용 안에 들어간다).
    return re.compile(rf"^{re.escape(stem)}(\.log(\.\d+)?|-[A-Za-z0-9._-]+\.log)$")


def fetch(container: str, name: str, inode: str, offset: int, length: int, env: dict[str, str]) -> bytes | None:
    """그 inode 의 [offset, offset+length) 를 읽는다. 그 사이 회전돼 이름이 사라졌거나 다른 파일이 됐으면 None.

    회전 직후에는 이름이 잠깐 없다(이름 바꾸기와 새 파일 만들기 사이). 그건 건너뛰고, 있는데 못 여는 것만 오류다.
    """
    script = (
        f"f='{trace.LOG_DIR}/{name}'; [ -e \"$f\" ] || exit {MOVED}; exec 3< \"$f\" || exit 3; "
        f"[ \"$(stat -Lc %i /proc/$$/fd/3)\" = {inode} ] || exit {MOVED}; "
        f"tail -c +{offset + 1} <&3 | head -c {length}"
    )
    done = _run(container, script, env, binary=True)
    if done.returncode == MOVED:
        return None
    if done.returncode != 0:
        raise PullError(f"{container}: {done.stderr.decode('utf-8', 'replace').strip() or f'exit {done.returncode}'}")
    return done.stdout


def local_files(directory: str, stem: str) -> list[tuple[str, int, str]]:
    """볼륨을 직접 붙인 경우(logarchive 컨테이너). (inode, 크기, 이름) 을 오래된 것부터."""
    pattern = _name_pattern(stem)
    try:
        names = os.listdir(directory)
    except OSError as error:
        raise PullError(f"{directory}: {type(error).__name__}: {error.strerror}") from None
    files = []
    for name in names:
        if not pattern.fullmatch(name):  # $ 는 이름 끝의 줄바꿈 앞에서도 맞는다 - fullmatch
            continue
        try:
            info = os.stat(os.path.join(directory, name), follow_symlinks=False)
        except FileNotFoundError:
            continue  # 목록을 읽은 사이 회전으로 사라졌다
        if statmod.S_ISREG(info.st_mode):  # 링크·특수 파일은 받지 않는다
            files.append((str(info.st_ino), info.st_size, name))
    files.sort(key=lambda item: trace._rotation_order(item[2], stem))
    return files


def local_fetch(directory: str, name: str, inode: str, offset: int, length: int) -> bytes | None:
    """fetch() 와 같은 약속을 파일로 직접: 연 뒤 inode 를 다시 확인해, 그 사이 회전됐으면 None."""
    try:
        fd = os.open(os.path.join(directory, name), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except FileNotFoundError:
        return None  # 회전 직후 이름이 잠깐 없다
    except OSError as error:
        raise PullError(f"{directory}/{name}: {type(error).__name__}: {error.strerror}") from None
    with os.fdopen(fd, "rb") as handle:
        if str(os.fstat(handle.fileno()).st_ino) != inode:
            return None
        handle.seek(offset)
        chunks, left = [], length
        while left > 0:  # 짧은 읽기는 이어서 - 쓰는 중인 파일이면 있는 만큼만
            block = handle.read(left)
            if not block:
                break
            chunks.append(block)
            left -= len(block)
        return b"".join(chunks)


def line_month(line: bytes, fallback: str) -> str:
    """줄의 시각(KST)으로 달을 정한다. 못 읽으면 받은 달."""
    record = trace.parse(line.decode("utf-8", "replace"))
    when = trace.record_time(record) if record else None
    if when is None:
        return fallback
    if when.tzinfo is None:
        when = when.replace(tzinfo=trace.KST)
    return when.astimezone(trace.KST).strftime("%Y-%m")


def append_by_month(folder: Path, stem: str, data: bytes, current: str, committed: dict[str, int]) -> None:
    """온전한 줄들을 달별 .log 에 이어 붙이고, 붙인 뒤의 크기를 committed 에 적는다(저장은 호출자가)."""
    groups: dict[str, list[bytes]] = {}
    for line in re.findall(rb"[^\n]*\n", data):  # 줄바꿈으로만 나눈다 - data 는 온전한 줄만 담겨 온다
        groups.setdefault(line_month(line, current), []).append(line)
    for month, lines in groups.items():
        path = folder / f"{stem}-{month}.log"
        with open(path, "ab") as handle:
            handle.write(b"".join(lines))
        committed[path.name] = path.stat().st_size


def roll_back_uncommitted(folder: Path, committed: dict[str, int]) -> None:
    """저장 전에 멈춘 실행이 붙인 꼬리를 잘라 되돌린다. 기록에 없는 보관 .log 는 통째로 미확정이다."""
    for path in folder.iterdir():
        match = ARCHIVE_FILE.match(path.name)
        if not match or match["gz"]:
            continue
        size = committed.get(path.name, 0)
        if path.stat().st_size > size:
            with open(path, "r+b") as handle:
                handle.truncate(size)
        if size == 0:
            path.unlink()
            committed.pop(path.name, None)


def archive(folder: Path, current: str, keep_months: int, committed: dict[str, int], save) -> None:
    """지난달 .log 는 조각 .gz 로, 보존 기간이 지난 달은 삭제."""
    year, month = map(int, current.split("-"))
    total = year * 12 + month - 1 - keep_months  # 이 달과 그 이전은 지운다
    newest_dropped = f"{total // 12:04d}-{total % 12 + 1:02d}"
    names = sorted(p.name for p in folder.iterdir())
    for name in names:
        match = ARCHIVE_FILE.match(name)
        if not match:
            continue  # pull.log · .state.json · 다른 파일은 건드리지 않는다
        path = folder / name
        if match["month"] <= newest_dropped:
            path.unlink()
            committed.pop(name, None)
            save()
        elif match["month"] < current and not match["gz"]:
            # 한 달치를 메모리에 올리지 않는다 - 컨테이너 메모리 상한 안에서 돈다(조각씩 해시·압축).
            hasher = hashlib.sha256()
            with open(path, "rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(block)
            digest = hasher.hexdigest()[:12]
            prefix = f"{match['stem']}-{match['month']}.p"
            existing = [n for n in names if n.startswith(prefix)]
            if not any(n.endswith(f"-{digest}.log.gz") for n in existing):
                number = 1 + max((int(ARCHIVE_FILE.match(n)["part"]) for n in existing), default=0)
                target = folder / f"{prefix}{number:02d}-{digest}.log.gz"
                temp = target.with_name(target.name + ".tmp")
                with open(path, "rb") as source, gzip.open(temp, "wb") as packed:
                    shutil.copyfileobj(source, packed, 1024 * 1024)
                temp.replace(target)
                names.append(target.name)
            path.unlink()  # 여기서 멈춰도 다음 실행이 같은 해시를 찾고 지우기만 한다
            committed.pop(name, None)
            save()


class Source(NamedTuple):
    """볼륨을 읽는 한 가지 방법. 원격(docker exec)이든 직접 마운트든 같은 약속을 지킨다."""

    name: str
    files: Callable[[str], list[tuple[str, int, str]]]  # stem → (inode, 크기, 이름) 오래된 것부터
    read: Callable[[str, str, int, int], bytes | None]  # (이름, inode, offset, length) → 바이트, 회전됐으면 None


def docker_source(container: str, env: dict[str, str]) -> Source:
    return Source(container, lambda stem: remote_files(container, stem, env),
                  lambda name, inode, offset, length: fetch(container, name, inode, offset, length, env))


def directory_source(directory: str) -> Source:
    return Source(directory, lambda stem: local_files(directory, stem),
                  lambda name, inode, offset, length: local_fetch(directory, name, inode, offset, length))


def pull_stream(stem: str, source: Source, state: dict[str, int], write, budget: int, save) -> tuple[int, int]:
    """한 스트림을 따라잡는다. (받은 바이트, 남은 예산)."""
    received = 0
    files = source.files(stem)
    alive = {inode for inode, _, _ in files}
    for inode in list(state):
        if inode not in alive:
            del state[inode]  # 서버에서 지워진 회전본
    for inode, size, name in files:
        offset = state.get(inode, 0)
        if size < offset:
            # ponytail: 같은 inode 가 새 파일에 재사용되면 크기가 줄어든다 - 처음부터 다시 받는다.
            # 재사용된 파일이 옛 위치보다 커질 때까지 5분 안에 자라면 못 알아챈다(20MB/5분이 필요해 현실적이지 않다).
            offset = 0
        if size == offset or budget <= 0:
            state[inode] = offset
            continue
        data = source.read(name, inode, offset, min(size - offset, budget))
        if data is None:
            continue  # 그 사이 회전됐다 - 위치를 그대로 두고 다음 실행에서 받는다
        complete = data[: data.rfind(b"\n") + 1]  # 반쪽 줄은 다음에
        if complete:
            write(complete)
        state[inode] = offset + len(complete)
        save()  # 위치와 확정 크기를 함께 기록. 붙인 뒤 여기 전에 멈추면 다음 시작 때 꼬리를 잘라 되돌린다
        received += len(complete)
        budget -= len(complete)
    return received, budget


class Lock:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self):
        try:
            # ponytail: 두 실행이 동시에 낡은 잠금을 지우면 뒤쪽이 앞쪽의 새 잠금을 지울 수 있다.
            # cron 5분 간격에 실행은 수 초라 겹치기 어렵다. 겹치면 flock 으로 바꾼다.
            if time.time() - self.path.stat().st_mtime > LOCK_STALE_SECONDS:
                self.path.unlink()  # 죽은 실행이 남긴 잠금
        except FileNotFoundError:
            pass
        try:
            os.close(os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            raise PullError("다른 실행이 진행 중이다 (잠금 파일 있음)") from None
        return self

    def __exit__(self, *_exc) -> None:
        self.path.unlink(missing_ok=True)


def pull(server: str, dest: Path, max_bytes: int, containers: list[str], *, label: str | None = None,
         keep_months: int = DEFAULT_KEEP_MONTHS, now: datetime | None = None,
         source_dir: str | None = None) -> dict[str, int]:
    if source_dir:
        sources = [directory_source(source_dir)]  # 볼륨을 직접 붙인 logarchive 컨테이너 - docker 가 필요 없다
    else:
        env = trace.docker_env(server)
        sources = [docker_source(container, env) for container in containers]
    folder = dest / (label or server)
    folder.mkdir(parents=True, exist_ok=True)
    current = (now or datetime.now(trace.KST)).astimezone(trace.KST).strftime("%Y-%m")
    state_path = folder / ".state.json"

    with Lock(folder / ".lock"):
        # 잠금을 잡은 뒤에 읽는다 - 앞선 실행이 막 저장한 위치를 봐야 한다.
        state: dict = json.loads(state_path.read_text("utf-8")) if state_path.exists() else {}
        if FILES_KEY not in state:
            # 상태가 없다(첫 실행이거나 지워졌다). 이미 있는 보관 파일은 확정으로 본다 - 되돌리며 지우지 않는다.
            state[FILES_KEY] = {p.name: p.stat().st_size for p in folder.iterdir()
                                if (m := ARCHIVE_FILE.match(p.name)) and not m["gz"]}
        committed: dict[str, int] = state[FILES_KEY]

        def save() -> None:
            temp = state_path.with_suffix(".tmp")
            temp.write_text(json.dumps(state, indent=1), "utf-8")
            temp.replace(state_path)

        roll_back_uncommitted(folder, committed)
        archive(folder, current, keep_months, committed, save)  # 멈췄던 압축을 새 줄이 섞이기 전에 마무리
        problems = []
        for source in sources:
            try:
                budget = max_bytes
                result = {}
                for stem in STEMS:
                    got, budget = pull_stream(
                        stem, source, state.setdefault(stem, {}),
                        lambda data, stem=stem: append_by_month(folder, stem, data, current, committed),
                        budget, save)
                    result[stem] = got
                save()
                break
            except PullError as error:
                problems.append(str(error))  # 이 컨테이너가 죽어 있으면 다른 컨테이너로 (둘 다 볼륨을 붙인다)
        else:
            raise PullError("볼륨을 읽지 못했다:\n  " + "\n  ".join(problems))
        archive(folder, current, keep_months, committed, save)
        return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="볼륨 로그를 텍스트 파일로 빼서 오래 보관")
    parser.add_argument("--server", default=None, choices=sorted(trace.SERVERS))
    parser.add_argument("--dev", dest="server", action="store_const", const="dev")
    parser.add_argument("--prod", dest="server", action="store_const", const="prod")
    parser.add_argument("--dest", default=os.environ.get("TRACE_LOCAL_DIR"),
                        help="보관 폴더. 그 아래 <label>/ 이 생긴다 (기본: TRACE_LOCAL_DIR)")
    parser.add_argument("--label", help="보관 폴더 안의 이름 (기본: 서버 이름). 개발서버 안에서 돌릴 때 --label dev")
    parser.add_argument("--keep-months", type=int, default=DEFAULT_KEEP_MONTHS,
                        help=f"이보다 오래된 달은 지운다 (기본 {DEFAULT_KEEP_MONTHS})")
    parser.add_argument("--max-mb", type=int, default=DEFAULT_MAX_MB, help="한 번에 받을 최대 크기")
    parser.add_argument("--container", default=trace.APP_CONTAINER)
    parser.add_argument("--edge-container", default=trace.EDGE_CONTAINER)
    parser.add_argument("--source-dir", help="볼륨을 직접 붙인 경로(logarchive 컨테이너: /var/log/travelhunter). 주면 docker 를 쓰지 않는다")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.dest:
        parser.error("--dest 또는 TRACE_LOCAL_DIR 가 필요하다")
    if args.keep_months < 1:
        parser.error("--keep-months 는 1 이상이다")
    server = args.server or trace.DEFAULT_SERVER
    # 백엔드가 죽어 있어도 Caddy 로 읽는다 - 장애 때 로그가 가장 필요하다.
    result = pull(server, Path(args.dest), max(1, args.max_mb) * 1024 * 1024, [args.edge_container, args.container],
                  label=args.label, keep_months=args.keep_months, source_dir=args.source_dir)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"{stamp} {args.label or server}: " + ", ".join(f"{stem} +{size / 1024:.1f}KB" for stem, size in result.items()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PullError as error:
        print(f"오류: {error}", file=sys.stderr)
        sys.exit(3)
