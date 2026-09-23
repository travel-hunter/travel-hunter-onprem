#!/usr/bin/env python3
"""역추적 로그 조회 - 엣지(Caddy)와 앱(백엔드) 로그를 한 시간축에 놓고 보여 준다.

계획: docs/superpowers/plans/2026-09-22-caddy-service-status-log.md (rev8)

  python scripts/trace.py 413dba2b-14a2-4ac5-8f4c-5bda8b037af3
  python scripts/trace.py user:42 --since 48h
  python scripts/trace.py <id> --server dev          # 개발서버 (SSH 너머 docker)
  python scripts/trace.py --summary --since 24h      # 시간대x상태군, 5xx 상위 경로
  python scripts/trace.py --tail                     # 실시간 따라가기
  python scripts/trace.py <id> --out trace.txt

엣지 줄과 앱 줄은 같은 ID 로 묶인다 - Caddy 가 만든 uuid 를 백엔드가 request_id 로 채택하기 때문이다.
Caddy 컨테이너가 없으면(로컬 직결 구성) 앱 줄만 보여 준다. 오류가 아니다.

안전: DOCKER_HOST 는 하위 프로세스 env 로만 넘긴다(셸에 export 하지 않는다). 부르는 docker 명령은
logs 와 inspect 뿐이다 - DOCKER_HOST=ssh 는 원격 Docker API 전체 권한이므로 조회 계열로 한정한다.

AWS 이전 후에는 같은 조건을 CloudWatch Logs Insights 로: filter request_id = "..." / filter user_id = 42
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
APP_CONTAINER = os.environ.get("TRACE_CONTAINER", "travel-hunter-onprem-backend-1")
EDGE_CONTAINER = os.environ.get("TRACE_EDGE_CONTAINER", "travel-hunter-onprem-caddy-1")
SERVERS = {"local": None, "dev": "ssh://dev-server", "prod": "ssh://prod-server"}


def docker_env(server: str) -> dict[str, str]:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    host = SERVERS.get(server)
    if host:
        env["DOCKER_HOST"] = host  # 하위 프로세스에만. 셸 환경은 건드리지 않는다.
    return env


def container_exists(name: str, env: dict[str, str]) -> bool:
    return subprocess.run(["docker", "inspect", name], capture_output=True, env=env).returncode == 0


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
    for line in (done.stdout + done.stderr).splitlines():
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


def app_rows(records, selector, sensitive: bool):
    for r in records:
        if "request_id" not in r:
            continue
        if not sensitive and r.get("kind") == "debug":
            continue
        if not selector(r):
            continue
        try:
            when = datetime.fromisoformat(r["ts"])
        except (ValueError, KeyError):
            continue
        yield when, "app", r


def edge_rows(records, key: str | None):
    for r in records:
        if not str(r.get("logger", "")).startswith("http.log.access"):
            continue
        if key is not None and r.get("uuid") != key:
            continue
        ts = r.get("ts")
        if not isinstance(ts, (int, float)):
            continue
        yield datetime.fromtimestamp(ts, tz=KST), "edge", r


def format_app(when: datetime, r: dict) -> str:
    stamp = when.astimezone(KST).strftime("%H:%M:%S.%f")[:-3]
    kind = r.get("kind")
    if kind == "access":
        head = (f"{stamp}  [app]  ACCESS {r.get('method')} {r.get('path')} "
                f"{r.get('status') if r.get('status') is not None else r.get('outcome')}  "
                f"{r.get('duration_ms', '-')}ms  user={r.get('user_id') or '-'}  rid={r.get('request_id')}")
        if r.get("body_shape") is not None:
            head += f"\n{' ' * 17}body_shape={json.dumps(r['body_shape'], ensure_ascii=False)}"
        return head
    if kind == "debug":
        return (f"{stamp}  [app]  DEBUG  {r.get('method')} {r.get('path')}  "
                f"body={json.dumps(r.get('debug_body'), ensure_ascii=False)}")
    out = f"{stamp}  [app]  {str(r.get('level', '')):<6} {r.get('logger')}  {r.get('msg')}"
    if r.get("exc_type"):
        out += f"\n{' ' * 17}↳ {r['exc_type']}: {r.get('exc_message')}"
    for frame in r.get("frames") or []:
        out += f"\n{' ' * 19}{frame}"
    for cause in r.get("causes") or []:
        out += f"\n{' ' * 17}↳ cause {cause.get('exc_type')}: {cause.get('exc_message')}"
    return out


def format_edge(when: datetime, r: dict) -> str:
    request = r.get("request", {})
    duration = r.get("duration")
    ms = f"{int(duration * 1000)}ms" if isinstance(duration, (int, float)) else "-"
    return (f"{when.strftime('%H:%M:%S')}      [edge] {request.get('method')} {request.get('uri')} "
            f"{r.get('status')}  {ms}  net={request.get('client_ip') or '-'}")


def render(rows) -> list[str]:
    lines = []
    for when, source, record in sorted(rows, key=lambda row: row[0]):
        lines.append(format_app(when, record) if source == "app" else format_edge(when, record))
    return lines


def summarize(records) -> list[str]:
    access = [r for r in records if r.get("kind") == "access" and r.get("status") is not None]
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


def main() -> int:
    parser = argparse.ArgumentParser(description="엣지·앱 로그 역추적", add_help=True)
    parser.add_argument("key", nargs="?", help="request_id 또는 user:<id>")
    parser.add_argument("--since", default="48h")
    parser.add_argument("--server", default="local", choices=sorted(SERVERS))
    parser.add_argument("--container", default=APP_CONTAINER)
    parser.add_argument("--edge-container", default=EDGE_CONTAINER)
    parser.add_argument("--app-only", action="store_true")
    parser.add_argument("--edge-only", action="store_true")
    parser.add_argument("--sensitive", action="store_true", help="kind=debug 줄까지 (출력 편의일 뿐 접근 통제가 아니다)")
    parser.add_argument("--summary", action="store_true", help="기간 요약 (앱 로그 기준)")
    parser.add_argument("--tail", action="store_true", help="실시간 따라가기")
    parser.add_argument("--out", help="결과를 파일로 저장")
    args = parser.parse_args()

    env = docker_env(args.server)
    if not container_exists(args.container, env):
        where = f"{args.server} 서버의 " if args.server != "local" else ""
        print(f"컨테이너를 찾지 못했다: {where}{args.container}", file=sys.stderr)
        return 2

    if args.summary:
        lines = summarize(list(read_logs(args.container, args.since, env)))
    elif args.tail:
        for record in read_logs(args.container, args.since, env, follow=True):
            if "request_id" in record and (args.sensitive or record.get("kind") != "debug"):
                try:
                    print(format_app(datetime.fromisoformat(record["ts"]), record), flush=True)
                except (ValueError, KeyError):
                    pass
        return 0
    else:
        if not args.key:
            parser.error("request_id 또는 user:<id> 가 필요하다 (--summary / --tail 은 예외)")
        if args.key.startswith("user:"):
            user_id = args.key[5:]
            app_selector = lambda r: str(r.get("user_id")) == user_id  # noqa: E731
            edge_key: str | None = "\0"  # 엣지 로그에는 사용자 정보가 없다 - 매칭되지 않는 값
        else:
            app_selector = lambda r: r.get("request_id") == args.key  # noqa: E731
            edge_key = args.key

        rows = []
        if not args.edge_only:
            rows += list(app_rows(read_logs(args.container, args.since, env), app_selector, args.sensitive))
        if not args.app_only and container_exists(args.edge_container, env):
            rows += list(edge_rows(read_logs(args.edge_container, args.since, env), edge_key))
        lines = render(rows)

    text = "\n".join(lines)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"{args.out} 에 {len(lines)}줄 저장")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
