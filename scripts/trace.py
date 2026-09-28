#!/usr/bin/env python3
"""역추적 로그 조회 - 엣지(Caddy)와 앱(백엔드) 로그를 한 시간축에 놓고 보여 준다.

계획: docs/superpowers/plans/2026-09-22-caddy-service-status-log.md (rev8)

  python scripts/trace.py 413dba2b-14a2-4ac5-8f4c-5bda8b037af3
  python scripts/trace.py user:42 --since 48h
  python scripts/trace.py --recent --since 24h       # 기간 내 활동 전체를 시간순으로
  python scripts/trace.py <id> --server dev          # 개발서버 (SSH 너머 docker)

짧게 쓰기 - 래퍼가 python scripts/ 를 대신한다(scripts/trace, scripts/trace.cmd):
  trace 413dba2b               # 문의 코드
  trace --recent --since 7d    # 활동 전체
  trace --stats                # 요약
  trace --dev --recent         # 개발서버 (TRACE_SERVER=dev 로 기본값 지정도 가능)
  python scripts/trace.py --summary --since 24h      # 시간대x상태군, 5xx 상위 경로
  python scripts/trace.py --tail                     # 실시간 따라가기
  python scripts/trace.py <id> --out trace.txt

기본 조회원은 볼륨에 쌓인 로그 파일이다 - 컨테이너 로그는 재배포·재부팅 때 사라지지만 볼륨은 남는다.
회전본(backend.log.N, caddy-access-<타임스탬프>-<사유>.log[.gz])까지 오래된 것부터 함께 읽는다.
--since 는 레코드의 ts 로 직접 거른다(기본 48h). 오래된 이력을 보려면 --since 30d 처럼 늘린다.
한 번에 읽는 양은 --max-mb 로 제한한다(기본 64MB, 초과 시 최근 쪽만 읽고 알림).
실시간(--tail)만 컨테이너 로그를 쓴다. --source 로 바꿀 수 있다.
읽기에 실패하면 빈 결과가 아니라 stderr 에 원인을 내고 종료 코드 3 으로 끝난다.

엣지 줄과 앱 줄은 같은 ID 로 묶인다 - Caddy 가 만든 uuid 를 백엔드가 request_id 로 채택하기 때문이다.
Caddy 컨테이너가 없으면(로컬 직결 구성) 앱 줄만 보여 준다. 오류가 아니다.

안전: DOCKER_HOST 는 하위 프로세스 env 로만 넘긴다(셸에 export 하지 않는다). 부르는 docker 명령은
logs · inspect · exec (ls/cat/gzip -dc, 고정 디렉터리) 뿐이다 - DOCKER_HOST=ssh 는 원격 Docker API 전체 권한이므로
조회 계열로 한정한다. exec 의 인자는 고정이고 읽기 전용이다.

AWS 이전 후에는 같은 조건을 CloudWatch Logs Insights 로: filter request_id = "..." / filter user_id = 42
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
APP_CONTAINER = os.environ.get("TRACE_CONTAINER", "travel-hunter-onprem-backend-1")
EDGE_CONTAINER = os.environ.get("TRACE_EDGE_CONTAINER", "travel-hunter-onprem-caddy-1")
SERVERS = {"local": None, "dev": "ssh://dev-server", "prod": "ssh://prod-server"}
DEFAULT_SERVER = os.environ.get("TRACE_SERVER", "local")  # 기본 대상. 옵션이 있으면 옵션이 이긴다
LOG_DIR = "/var/log/travelhunter"
APP_STEM = "backend"
EDGE_STEM = "caddy-access"
DEFAULT_MAX_MB = 64


# 색은 터미널일 때만. 파이프·--out 이면 끈다(NO_COLOR 도 존중).
_ANSI = {"red": "31", "yellow": "33", "green": "32", "cyan": "36", "magenta": "35", "dim": "2", "bold": "1"}
_USE_COLOR = False


def set_color_mode(mode: str) -> None:
    global _USE_COLOR
    if mode == "never" or os.environ.get("NO_COLOR"):
        _USE_COLOR = False
    elif mode == "always":
        _USE_COLOR = True
    else:
        _USE_COLOR = sys.stdout.isatty()


def paint(text: str, *styles: str) -> str:
    if not _USE_COLOR or not styles:
        return text
    codes = ";".join(_ANSI[s] for s in styles if s in _ANSI)
    return f"\033[{codes}m{text}\033[0m" if codes else text


def status_styles(status) -> tuple[str, ...]:
    """5xx 빨강, 4xx 노랑, 그 외는 기본. 눈이 먼저 오류로 가게 한다."""
    try:
        code = int(status)
    except (TypeError, ValueError):
        return ("magenta",) if status else ()  # outcome 문자열(cancelled 등)
    if code >= 500:
        return ("red", "bold")
    if code >= 400:
        return ("yellow",)
    return ()


def short_id(value, full: bool) -> str:
    """UUID 36자가 줄의 절반을 먹는다. 앞 8자면 구별에 충분하다."""
    text = str(value or "-")
    return text if full or len(text) <= 8 else text[:8]


def docker_env(server: str) -> dict[str, str]:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    host = SERVERS.get(server)
    if host:
        env["DOCKER_HOST"] = host  # 하위 프로세스에만. 셸 환경은 건드리지 않는다.
    return env


def container_exists(name: str, env: dict[str, str]) -> bool:
    return subprocess.run(["docker", "inspect", name], capture_output=True, env=env).returncode == 0


class LogReadError(RuntimeError):
    """볼륨 로그를 읽지 못했다. '파일이 비었다'와 구분해야 하므로 예외로 올린다."""


def parse_since(spec: str) -> datetime | None:
    """docker 와 같은 표기를 받는다: 90s · 30m · 48h · 7d · 1h30m, 또는 ISO 8601."""
    if not spec:
        return None
    text = spec.strip()
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    parts = re.findall(r"(\d+)([smhd])", text)
    if parts and "".join(f"{n}{u}" for n, u in parts) == text:
        delta = sum((timedelta(**{units[u]: int(n)}) for n, u in parts), timedelta())
        return datetime.now(KST) - delta
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise LogReadError(f"--since 를 해석하지 못했다: {spec!r} (예: 2h, 7d, 1h30m, 2026-09-28T09:00+09:00)") from error
    return moment if moment.tzinfo else moment.replace(tzinfo=KST)


def record_time(record: dict) -> datetime | None:
    """앱 줄은 ISO 문자열 ts, 엣지(Caddy) 줄은 epoch 초다."""
    ts = record.get("ts")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, tz=KST)
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return None
    return None


def _rotation_order(name: str, stem: str) -> tuple:
    """오래된 것 → 최신 순. 현재 파일이 가장 마지막에 오게 한다.

    백엔드(RotatingFileHandler): backend.log.1 … backend.log.10  — 숫자가 클수록 오래됐다.
      문자열 정렬이면 .10 이 .2 앞에 오므로 숫자로 정렬한다.
    Caddy(lumberjack): caddy-access-2026-09-28T03-56-10.890-size.log — 이름의 타임스탬프가 순서다.
    """
    if name == f"{stem}.log":
        return (2, "")  # 현재 파일이 가장 최신
    numbered = re.fullmatch(rf"{re.escape(stem)}\.log\.(\d+)(?:\.gz)?", name)
    if numbered:
        return (0, -int(numbered.group(1)))  # .10 이 .1 보다 오래됐다
    return (1, name)  # caddy 회전본 - 이름의 타임스탬프가 사전순으로 시간순이다


def _failure(done) -> str:
    """실패 원인. 메시지가 비면 '로그 없음'으로 오해되니 종료 코드라도 남긴다."""
    return (done.stderr or done.stdout).strip() or f"exit {done.returncode}"


def _lines(text: str) -> list[str]:
    """splitlines() 는 U+2028 등에서도 나눈다. 경로에 그 문자를 넣은 요청이 쪼개져 사라지지 않게 줄바꿈으로만 자른다."""
    return text.split("\n")


def list_rotated(container: str, stem: str, env: dict[str, str]) -> tuple[list[str], str]:
    """디렉터리를 훑어 이 stem 의 현재 파일과 회전본을 오래된 것부터 돌려준다."""
    done = subprocess.run(["docker", "exec", container, "sh", "-c", f"ls -1 {LOG_DIR}"],
                          capture_output=True, encoding="utf-8", errors="replace", env=env)
    if done.returncode != 0:
        return [], _failure(done)
    # 이름이 sh -c '…' 인용 안에 들어가므로 따옴표·공백·셸 문자가 섞인 이름은 받지 않는다.
    pattern = re.compile(rf"^{re.escape(stem)}(\.log(\.\d+)?|-[A-Za-z0-9._-]+\.log)(\.gz)?$")
    # ls -1 은 한 줄에 하나다. 공백으로 쪼개면 이상한 이름이 우연히 걸러질 뿐
    # 정규식이 방어선 역할을 못 한다. 줄 단위로 읽고 정규식이 거르게 한다.
    names = [n for n in (n.strip() for n in _lines(done.stdout)) if pattern.match(n)]
    names.sort(key=lambda n: _rotation_order(n, stem))
    return [f"{LOG_DIR}/{n}" for n in names], ""


def read_volume_file(stem: str, env: dict[str, str], containers: list[str], max_bytes: int):
    """볼륨의 로그 파일을 회전본까지 오래된 것부터 읽는다.

    docker exec 로 읽으므로 DOCKER_HOST=ssh 가 그대로 적용되고 호스트 파일 권한을 건드리지 않는다.
    백엔드가 죽어 있을 수 있으니 컨테이너를 순서대로 시도하고, 전부 실패하면 예외를 올린다 -
    읽기 실패를 '로그 없음'으로 오해하면 안 된다.
    """
    problems = []
    for container in containers:
        files, error = list_rotated(container, stem, env)
        if error:
            problems.append(f"{container}: {error}")
            continue
        if not files:
            return  # 컨테이너는 읽었는데 파일이 없다 - 정상적인 '비어 있음'
        # 상한을 넘으면 최근 쪽을 남긴다. 잘린 첫 줄은 아래에서 버린다.
        quoted = " ".join(f"'{f}'" for f in files)
        script = (f"for f in {quoted}; do case \"$f\" in *.gz) gzip -dc \"$f\";; *) cat \"$f\";; esac; "
                  f"done | tail -c {max_bytes}")
        done = subprocess.run(["docker", "exec", container, "sh", "-c", script],
                              capture_output=True, encoding="utf-8", errors="replace", env=env)
        if done.returncode != 0:
            problems.append(f"{container}: {_failure(done)}")
            continue
        lines = _lines(done.stdout)
        if len(done.stdout.encode("utf-8", "replace")) >= max_bytes and lines:
            lines = lines[1:]  # 상한에 걸려 앞이 잘렸다 - 깨진 첫 줄을 버린다
            print(f"[알림] {stem}: 최근 {max_bytes // 1024 // 1024}MB 만 읽었다. --max-mb 로 늘릴 수 있다.",
                  file=sys.stderr)
        for line in lines:
            record = parse(line)
            if record is not None:
                yield record
        return
    raise LogReadError("볼륨 로그를 읽지 못했다 (컨테이너 접근 실패):\n  " + "\n  ".join(problems or ["대상 컨테이너 없음"]))


def read_logs(name: str, since: str, env: dict[str, str], follow: bool = False):
    """docker logs 를 JSON 줄로 읽는다. Windows 기본 인코딩으로 읽으면 한글이 깨지므로 utf-8 을 명시한다."""
    cmd = ["docker", "logs", "--since", since] + (["--follow"] if follow else []) + [name]
    if follow:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                encoding="utf-8", errors="replace", env=env, bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            record = parse(line)
            if record is not None:
                yield record
        return
    done = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", env=env)
    for line in _lines(done.stdout + done.stderr):
        record = parse(line)
        if record is not None:
            yield record


def parse(line: str):
    line = line.strip()
    if not line.startswith("{"):
        return None  # 기동 배너 등 비 JSON 줄
    try:
        return json.loads(line)
    except ValueError:
        return None


def app_rows(records, selector, sensitive: bool, cutoff: datetime | None = None):
    for r in records:
        if "request_id" not in r:
            continue
        if not sensitive and r.get("kind") == "debug":
            continue
        if not selector(r):
            continue
        when = record_time(r)
        if when is None or (cutoff is not None and when < cutoff):
            continue
        yield when, "app", r


def edge_rows(records, key: str | None, cutoff: datetime | None = None):
    for r in records:
        if not str(r.get("logger", "")).startswith("http.log.access"):
            continue
        if key is not None and r.get("uuid") != key:
            continue
        when = record_time(r)
        if when is None or (cutoff is not None and when < cutoff):
            continue
        yield when, "edge", r


INDENT = " " * 19  # 이어지는 줄(예외·프레임)이 본문과 나란히 서게


def _source_tag(source: str) -> str:
    """색 코드가 들어가면 len() 이 늘어 열이 어긋난다. 폭을 먼저 맞추고 칠한다."""
    styles = ("cyan",) if source == "app" else ("magenta",)
    return paint(f"[{source}]".ljust(6), *styles)


def _row(stamp: str, source: str, kind: str, status, ms, rest: str) -> str:
    """열 폭을 맞춰 표처럼. 소요시간은 오른쪽 정렬이라 크기 비교가 된다."""
    duration = f"{ms}ms" if ms not in (None, "-", "") else "-"
    # f-string 안에서 바깥과 같은 따옴표를 다시 쓰면 3.12 에서만 파싱된다(PEP 701). 값을 먼저 만든다.
    status_text = "" if status is None else str(status)
    return (f"{paint(stamp, 'dim')}  {_source_tag(source)} {kind:<6} "
            f"{paint(status_text.rjust(5), *status_styles(status))} "
            f"{duration:>7}  {rest}")


def format_app(when: datetime, r: dict, full_id: bool = False) -> str:
    stamp = when.astimezone(KST).strftime("%H:%M:%S.%f")[:-3]
    kind = r.get("kind")
    if kind == "access":
        status = r.get("status") if r.get("status") is not None else r.get("outcome")
        rest = (f"{r.get('method')} {r.get('path')}  "
                f"{paint('user=' + str(r.get('user_id') or '-'), 'dim')} "
                f"{paint('rid=' + short_id(r.get('request_id'), full_id), 'dim')}")
        head = _row(stamp, "app", "ACCESS", status, r.get("duration_ms"), rest)
        if r.get("body_shape") is not None:
            head += f"\n{INDENT}body_shape={json.dumps(r['body_shape'], ensure_ascii=False)}"
        return head
    if kind == "debug":
        return _row(stamp, "app", "DEBUG", "", None,
                    f"{r.get('method')} {r.get('path')}  body={json.dumps(r.get('debug_body'), ensure_ascii=False)}")

    level = str(r.get("level", ""))
    level_styles = ("red", "bold") if level == "ERROR" else ("yellow",) if level == "WARNING" else ("dim",)
    out = (f"{paint(stamp, 'dim')}  {_source_tag('app')} {paint(f'{level:<6}', *level_styles)} "
           f"{paint(str(r.get('logger')), 'dim')}  {r.get('msg')}")
    if r.get("exc_type"):
        out += f"\n{INDENT}{paint('↳ ' + str(r['exc_type']) + ': ' + str(r.get('exc_message')), 'red')}"
    for frame in r.get("frames") or []:
        out += f"\n{INDENT}  {paint(str(frame), 'dim')}"
    for cause in r.get("causes") or []:
        out += f"\n{INDENT}{paint('↳ cause ' + str(cause.get('exc_type')) + ': ' + str(cause.get('exc_message')), 'dim')}"
    return out


def format_edge(when: datetime, r: dict, full_id: bool = False) -> str:
    request = r.get("request", {})
    duration = r.get("duration")
    ms = int(duration * 1000) if isinstance(duration, (int, float)) else None
    rest = (f"{request.get('method')} {request.get('uri')}  "
            f"{paint('net=' + str(request.get('client_ip') or '-'), 'dim')}")
    return _row(when.strftime("%H:%M:%S") + "    ", "edge", "", r.get("status"), ms, rest)


def render(rows, full_id: bool = False) -> list[str]:
    lines = []
    for when, source, record in sorted(rows, key=lambda row: row[0]):
        lines.append(format_app(when, record, full_id) if source == "app" else format_edge(when, record, full_id))
    return lines


def summarize(records, cutoff: datetime | None = None) -> list[str]:
    access = [r for r in records if r.get("kind") == "access" and r.get("status") is not None]
    if cutoff is not None:
        access = [r for r in access if (t := record_time(r)) is not None and t >= cutoff]
    if not access:
        return ["접근 줄 없음 - 이 기간에 기록된 요청이 없다"]
    buckets: dict[tuple[str, str], list[int]] = defaultdict(list)
    for r in access:
        hour = str(r.get("ts", ""))[:13]
        buckets[(hour, f"{int(r['status']) // 100}xx")].append(int(r.get("duration_ms") or 0))
    out = ["== 시간대 x 상태군 (건수 / 평균 / 최대) =="]
    for (hour, cls), values in sorted(buckets.items()):
        out.append(f"{hour}  {cls}  {len(values):<5} avg {sum(values) // len(values)}ms  max {max(values)}ms")

    failures = [r for r in access if int(r["status"]) >= 500]
    out += ["", "== 5xx 상위 경로 =="]
    if failures:
        by_path: dict[str, int] = defaultdict(int)
        for r in failures:
            by_path[str(r.get("path"))] += 1
        for path, count in sorted(by_path.items(), key=lambda kv: -kv[1])[:10]:
            out.append(f"{count:<5} {path}")
        out += ["", "== 최근 5xx (rid 로 다시 추적) =="]
        for r in failures[-20:]:
            out.append(f"{str(r.get('ts'))[11:19]}  {r.get('method')} {r.get('path')} {r.get('status')}  "
                       f"user={r.get('user_id') or '-'}  rid={r.get('request_id')}")
    else:
        out.append("(없음)")
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="엣지·앱 로그 역추적", add_help=True)
    parser.add_argument("key", nargs="?", help="request_id 또는 user:<id>")
    parser.add_argument("--since", default="48h")
    parser.add_argument("--server", default=None, choices=sorted(SERVERS),
                        help=f"대상 서버 (기본 {DEFAULT_SERVER}, TRACE_SERVER 환경변수로 바꾼다)")
    parser.add_argument("--dev", dest="server", action="store_const", const="dev", help="--server dev 의 짧은 형태")
    parser.add_argument("--prod", dest="server", action="store_const", const="prod", help="--server prod 의 짧은 형태")
    parser.add_argument("--container", default=APP_CONTAINER)
    parser.add_argument("--edge-container", default=EDGE_CONTAINER)
    parser.add_argument("--app-only", action="store_true")
    parser.add_argument("--edge-only", action="store_true")
    parser.add_argument("--sensitive", action="store_true", help="kind=debug 줄까지 (출력 편의일 뿐 접근 통제가 아니다)")
    parser.add_argument("--recent", action="store_true", help="기간 내 전체 활동을 시간순으로 (엣지+앱, 출력 후 종료)")
    parser.add_argument("--summary", "--stats", dest="summary", action="store_true",
                        help="기간 요약 (앱 로그 기준). --stats 로도 쓴다")
    parser.add_argument("--tail", action="store_true", help="실시간 따라가기")
    parser.add_argument("--out", help="결과를 파일로 저장")
    parser.add_argument("--color", default="auto", choices=("auto", "always", "never"),
                        help="색 출력. auto=터미널일 때만(파이프·--out 이면 끔)")
    parser.add_argument("--full-id", action="store_true", help="request_id 를 앞 8자로 줄이지 않는다")
    parser.add_argument("--max-mb", type=int, default=DEFAULT_MAX_MB,
                        help=f"볼륨 로그를 한 번에 읽을 최대 크기(MB, 기본 {DEFAULT_MAX_MB}). 넘으면 최근 쪽만 읽는다")
    parser.add_argument("--source", default="volume", choices=("volume", "docker"),
                        help="volume=볼륨의 로그 파일(재배포를 넘어선 이력, 기본) / docker=컨테이너 로그(최근 것만, "
                             "Caddy 접근 줄은 볼륨에만 있어 앱 줄만 나온다)")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    server = args.server or DEFAULT_SERVER
    set_color_mode("never" if args.out else args.color)
    env = docker_env(server)
    if not container_exists(args.container, env):
        where = f"{server} 서버의 " if server != "local" else ""
        print(f"컨테이너를 찾지 못했다: {where}{args.container}", file=sys.stderr)
        return 2

    # 볼륨 파일에는 docker 의 --since 가 없다. 레코드의 ts 로 직접 거른다(cutoff).
    containers = [args.container, args.edge_container]
    max_bytes = max(1, args.max_mb) * 1024 * 1024
    cutoff = parse_since(args.since) if args.source == "volume" else None

    def app_source():
        if args.source == "volume":
            return read_volume_file(APP_STEM, env, containers, max_bytes)
        return read_logs(args.container, args.since, env)

    def edge_source():
        if args.source == "volume":
            return read_volume_file(EDGE_STEM, env, containers, max_bytes)
        return read_logs(args.edge_container, args.since, env)

    if args.summary:
        lines = summarize(list(app_source()), cutoff)
    elif args.tail:
        for record in read_logs(args.container, args.since, env, follow=True):
            if "request_id" in record and (args.sensitive or record.get("kind") != "debug"):
                try:
                    print(format_app(datetime.fromisoformat(record["ts"]), record, args.full_id), flush=True)
                except (ValueError, KeyError):
                    pass
        return 0
    else:
        edge_key: str | None
        if args.recent:
            # 기간 내 전체. 키 기반 경로를 그대로 쓰되 선택자를 열어 둔다.
            app_selector = lambda r: True  # noqa: E731
            edge_key = None  # edge_rows 는 None 을 "전체" 로 본다
        elif not args.key:
            parser.error("request_id 또는 user:<id> 가 필요하다 (--recent / --summary / --tail 은 예외)")
        elif args.key.startswith("user:"):
            user_id = args.key[5:]
            app_selector = lambda r: str(r.get("user_id")) == user_id  # noqa: E731
            edge_key = "\0"  # 엣지 로그에는 사용자 정보가 없다 - 매칭되지 않는 값
        else:
            app_selector = lambda r: r.get("request_id") == args.key  # noqa: E731
            edge_key = args.key

        rows = []
        if not args.edge_only:
            rows += list(app_rows(app_source(), app_selector, args.sensitive, cutoff))
        if not args.app_only and (args.source == "volume" or container_exists(args.edge_container, env)):
            rows += list(edge_rows(edge_source(), edge_key, cutoff))
        lines = render(rows, args.full_id)

    text = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"{args.out} 에 {len(lines)}줄 저장")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LogReadError as error:
        print(f"오류: {error}", file=sys.stderr)
        sys.exit(3)
