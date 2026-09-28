"""scripts/trace.py 회귀 테스트 — 볼륨 로그 조회의 동작을 고정한다.

계획: docs/superpowers/plans/2026-09-22-caddy-service-status-log.md (rev12)

Docker 없이 돈다. subprocess.run 을 가짜로 바꿔 파일 목록·내용·실패를 흉내 낸다.
고정하는 것: --since 필터 · Caddy 회전 파일명(.gz 포함) · 회전 정렬 · 읽기 실패 시 예외 · 읽기 상한.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

TRACE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "trace.py"


def _load():
    spec = importlib.util.spec_from_file_location("trace_script", TRACE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


trace = _load()
KST = trace.KST


# ----------------------------------------------------------------- 가짜 docker
class FakeDocker:
    """docker exec 를 흉내 낸다. ls 와 본문 읽기에 각각 답한다."""

    def __init__(self, listing: dict[str, list[str]] | None = None,
                 payload: dict[str, str] | None = None,
                 fail: set[str] | None = None,
                 silent_fail: set[str] | None = None):
        self.listing = listing or {}
        self.payload = payload or {}
        self.fail = fail or set()
        self.silent_fail = silent_fail or set()  # 실패하되 메시지가 없다 (볼륨 없는 옛 배포본)
        self.commands: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.commands.append(cmd)
        container = cmd[2] if len(cmd) > 2 else ""
        script = cmd[-1]
        if container in self.fail:
            return SimpleNamespace(returncode=1, stdout="", stderr=f"container {container} is not running")
        if container in self.silent_fail:
            return SimpleNamespace(returncode=2, stdout="", stderr="")
        if script.startswith("ls -1"):
            return SimpleNamespace(returncode=0, stdout="\n".join(self.listing.get(container, [])), stderr="")
        return SimpleNamespace(returncode=0, stdout=self.payload.get(container, ""), stderr="")


def app_line(ts: str, **extra) -> str:
    return json.dumps({"ts": ts, "kind": "access", "request_id": "r1", "method": "GET",
                       "path": "/api/x", "status": 200, "duration_ms": 5, **extra}, ensure_ascii=False)


def edge_line(epoch: float, uuid: str = "u1", uri: str = "/asset.js") -> str:
    return json.dumps({"level": "info", "ts": epoch, "logger": "http.log.access.log0", "uuid": uuid,
                       "request": {"method": "GET", "uri": uri, "client_ip": "10.0.0.0"},
                       "status": 200, "duration": 0.01})


# ----------------------------------------------------------------- parse_since
@pytest.mark.parametrize("spec, expected", [
    ("90s", timedelta(seconds=90)),
    ("30m", timedelta(minutes=30)),
    ("2h", timedelta(hours=2)),
    ("7d", timedelta(days=7)),
    ("1h30m", timedelta(hours=1, minutes=30)),
    ("48h", timedelta(hours=48)),
])
def test_parse_since_durations(spec, expected):
    delta = datetime.now(KST) - trace.parse_since(spec)
    assert abs(delta - expected) < timedelta(seconds=5)


def test_parse_since_iso_with_and_without_offset():
    assert trace.parse_since("2026-09-28T09:00:00+09:00").hour == 9
    naive = trace.parse_since("2026-09-28T09:00:00")
    assert naive.tzinfo == KST, "시간대가 없으면 KST 로 읽는다 - 앱 로그가 KST 이므로"


def test_parse_since_rejects_garbage():
    with pytest.raises(trace.LogReadError):
        trace.parse_since("어제쯤")


def test_parse_since_empty_means_no_cutoff():
    assert trace.parse_since("") is None


# ----------------------------------------------------------------- record_time
def test_record_time_reads_both_shapes():
    assert trace.record_time({"ts": "2026-09-28T12:00:00+09:00"}).hour == 12
    assert trace.record_time({"ts": 1790000000.0}).tzinfo == KST  # 엣지 줄은 epoch
    assert trace.record_time({"ts": "not-a-time"}) is None
    assert trace.record_time({}) is None


# ----------------------------------------------------------------- 회전 정렬
def test_backend_rotation_sorts_numerically_not_lexically():
    # 문자열 정렬이면 .10 이 .2 앞에 온다. 숫자가 클수록 오래된 파일이다.
    names = ["backend.log", "backend.log.1", "backend.log.2", "backend.log.9", "backend.log.10"]
    ordered = sorted(names, key=lambda n: trace._rotation_order(n, "backend"))
    assert ordered == ["backend.log.10", "backend.log.9", "backend.log.2", "backend.log.1", "backend.log"]


def test_caddy_rotation_sorts_by_timestamp_with_current_file_last():
    # lumberjack 실제 형식: <이름>-<UTC 타임스탬프>-<사유>.log
    names = [
        "caddy-access.log",
        "caddy-access-2026-09-28T03-56-10.890-size.log",
        "caddy-access-2026-09-27T01-00-00.000-size.log",
    ]
    ordered = sorted(names, key=lambda n: trace._rotation_order(n, "caddy-access"))
    assert ordered == [
        "caddy-access-2026-09-27T01-00-00.000-size.log",
        "caddy-access-2026-09-28T03-56-10.890-size.log",
        "caddy-access.log",
    ]


# ----------------------------------------------------------------- 파일 탐색
def test_list_rotated_matches_real_caddy_names_and_gz(monkeypatch):
    fake = FakeDocker(listing={"c": [
        "caddy-access.log",
        "caddy-access-2026-09-28T03-56-10.890-size.log",
        "caddy-access-2026-09-27T01-00-00.000-size.log.gz",
        "backend.log", "backend.log.1",          # 다른 stem 은 섞이지 않는다
        "caddy-access.log.swp", "README",         # 로그가 아닌 파일도 배제
    ]})
    monkeypatch.setattr(subprocess, "run", fake)
    files, error = trace.list_rotated("c", "caddy-access", {})
    assert error == ""
    assert [Path(f).name for f in files] == [
        "caddy-access-2026-09-27T01-00-00.000-size.log.gz",
        "caddy-access-2026-09-28T03-56-10.890-size.log",
        "caddy-access.log",
    ]


def test_list_rotated_reports_failure_instead_of_empty(monkeypatch):
    monkeypatch.setattr(subprocess, "run", FakeDocker(fail={"c"}))
    files, error = trace.list_rotated("c", "backend", {})
    assert files == [] and "not running" in error


# ----------------------------------------------------------------- 읽기
def test_read_volume_file_decompresses_gz_and_orders_oldest_first(monkeypatch):
    fake = FakeDocker(listing={"c": ["backend.log", "backend.log.1"]},
                      payload={"c": app_line("2026-09-28T10:00:00+09:00") + "\n" + app_line("2026-09-28T11:00:00+09:00")})
    monkeypatch.setattr(subprocess, "run", fake)
    records = list(trace.read_volume_file("backend", {}, ["c"], 64 * 1024 * 1024))
    assert len(records) == 2
    script = fake.commands[-1][-1]
    assert "gzip -dc" in script, ".gz 를 만나면 풀어 읽을 수 있어야 한다"
    assert script.index("backend.log.1") < script.index("'/var/log/travelhunter/backend.log'"), "오래된 것부터"


def test_read_volume_file_raises_when_every_container_fails(monkeypatch):
    monkeypatch.setattr(subprocess, "run", FakeDocker(fail={"a", "b"}))
    with pytest.raises(trace.LogReadError) as error:
        list(trace.read_volume_file("backend", {}, ["a", "b"], 1024))
    assert "a:" in str(error.value) and "b:" in str(error.value), "컨테이너별 원인을 보여 준다"


def test_read_volume_file_falls_back_to_second_container(monkeypatch):
    fake = FakeDocker(listing={"b": ["backend.log"]},
                      payload={"b": app_line("2026-09-28T10:00:00+09:00")}, fail={"a"})
    monkeypatch.setattr(subprocess, "run", fake)
    assert len(list(trace.read_volume_file("backend", {}, ["a", "b"], 1024 * 1024))) == 1


def test_silent_failure_is_still_a_failure(monkeypatch):
    """볼륨이 없는 옛 배포본: ls 가 메시지 없이 실패해도 '로그 없음'이 아니라 실패다 (rev16)."""
    fake = FakeDocker(listing={"b": ["backend.log"]},
                      payload={"b": app_line("2026-09-28T10:00:00+09:00")}, silent_fail={"a"})
    monkeypatch.setattr(subprocess, "run", fake)
    assert len(list(trace.read_volume_file("backend", {}, ["a", "b"], 1024 * 1024))) == 1, "다음 컨테이너로 넘어간다"
    assert "2>" not in fake.commands[0][-1], "실패 메시지를 버리지 않는다"

    monkeypatch.setattr(subprocess, "run", FakeDocker(silent_fail={"a"}))
    with pytest.raises(trace.LogReadError) as error:
        list(trace.read_volume_file("backend", {}, ["a"], 1024))
    assert "exit 2" in str(error.value)


def test_line_separator_in_a_path_does_not_split_the_record(monkeypatch):
    """U+2028 은 json.dumps(ensure_ascii=False) 가 그대로 둔다. 그 문자로 줄이 쪼개지면 요청이 조회에서 사라진다."""
    line = app_line("2026-09-28T10:00:00+09:00", path="/\u2028x")
    assert "\u2028" in line
    monkeypatch.setattr(subprocess, "run", FakeDocker(listing={"c": ["backend.log"]}, payload={"c": line}))
    records = list(trace.read_volume_file("backend", {}, ["c"], 1024 * 1024))
    assert [r["path"] for r in records] == ["/\u2028x"]


def test_missing_file_is_empty_not_an_error(monkeypatch):
    """컨테이너는 읽혔는데 파일이 없다 - '로그 없음'이지 실패가 아니다."""
    monkeypatch.setattr(subprocess, "run", FakeDocker(listing={"c": ["other.txt"]}))
    assert list(trace.read_volume_file("backend", {}, ["c"], 1024)) == []


def test_max_bytes_drops_the_truncated_first_line(monkeypatch, capsys):
    # 상한에 걸리면 앞이 잘려 첫 줄이 깨진다. 그 줄을 버려야 한다.
    # 첫 줄을 올바른 JSON 으로 둔다 - 깨진 JSON 이면 버리지 않아도 parse 가 걸러 테스트가 의미 없다.
    good = app_line("2026-09-28T10:00:00+09:00")
    payload = app_line("2026-09-28T09:00:00+09:00") + "\n" + good
    fake = FakeDocker(listing={"c": ["backend.log"]}, payload={"c": payload})
    monkeypatch.setattr(subprocess, "run", fake)
    records = list(trace.read_volume_file("backend", {}, ["c"], len(payload.encode())))
    assert len(records) == 1 and records[0]["ts"] == "2026-09-28T10:00:00+09:00"
    assert "MB 만 읽었다" in capsys.readouterr().err, "잘렸으면 알린다"
    assert f"tail -c {len(payload.encode())}" in fake.commands[-1][-1]


# ----------------------------------------------------------------- --since 필터
def test_cutoff_filters_app_and_edge_rows():
    cutoff = datetime(2026, 9, 28, 12, 0, tzinfo=KST)
    app_records = [json.loads(app_line("2026-09-23T16:00:00+09:00")),
                   json.loads(app_line("2026-09-28T13:00:00+09:00"))]
    kept = list(trace.app_rows(app_records, lambda r: True, False, cutoff))
    assert [r[2]["ts"] for r in kept] == ["2026-09-28T13:00:00+09:00"]

    old = datetime(2026, 9, 23, 16, 0, tzinfo=KST).timestamp()
    new = datetime(2026, 9, 28, 13, 0, tzinfo=KST).timestamp()
    edge_records = [json.loads(edge_line(old)), json.loads(edge_line(new, uri="/kept.js"))]
    kept_edge = list(trace.edge_rows(edge_records, None, cutoff))
    assert [r[2]["request"]["uri"] for r in kept_edge] == ["/kept.js"]


def test_no_cutoff_keeps_everything():
    records = [json.loads(app_line("2026-09-23T16:00:00+09:00"))]
    assert len(list(trace.app_rows(records, lambda r: True, False, None))) == 1


def test_summary_applies_the_same_cutoff():
    cutoff = datetime(2026, 9, 28, 12, 0, tzinfo=KST)
    records = [json.loads(app_line("2026-09-23T16:00:00+09:00")),
               json.loads(app_line("2026-09-28T13:00:00+09:00"))]
    text = "\n".join(trace.summarize(records, cutoff))
    assert "2026-09-28T13" in text and "2026-09-23" not in text


def test_summary_drops_records_without_a_readable_time():
    """다른 모드처럼 시각을 못 읽은 줄은 기간 필터를 통과하지 않는다."""
    cutoff = datetime(2026, 9, 28, 12, 0, tzinfo=KST)
    records = [json.loads(app_line("알 수 없음"))]
    assert trace.summarize(records, cutoff)[0].startswith("접근 줄 없음")


def test_debug_lines_need_the_sensitive_flag():
    records = [{"ts": "2026-09-28T13:00:00+09:00", "kind": "debug", "request_id": "r1",
                "method": "POST", "path": "/api/x", "debug_body": {"a": 1}}]
    assert list(trace.app_rows(records, lambda r: True, False, None)) == []
    assert len(list(trace.app_rows(records, lambda r: True, True, None))) == 1


# ----------------------------------------------------------------- 색·정렬 (rev13)
@pytest.fixture(autouse=True)
def _plain_output():
    """기본은 색 없음. 색을 보는 테스트만 직접 켠다."""
    trace.set_color_mode("never")
    yield
    trace.set_color_mode("never")


def test_color_is_off_when_not_a_terminal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(trace.sys, "stdout", SimpleNamespace(isatty=lambda: False))
    trace.set_color_mode("auto")
    assert trace.paint("x", "red") == "x", "파이프·--out 이면 ANSI 코드가 섞이면 안 된다"


def test_no_color_env_wins_over_always(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    trace.set_color_mode("always")
    assert trace.paint("x", "red") == "x"


def test_color_always_paints(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    trace.set_color_mode("always")
    assert trace.paint("x", "red") == "\033[31mx\033[0m"


@pytest.mark.parametrize("status, styles", [
    (500, ("red", "bold")), (503, ("red", "bold")),
    (404, ("yellow",)), (422, ("yellow",)),
    (200, ()), (302, ()),
    ("cancelled", ("magenta",)), (None, ()),
])
def test_status_styles_highlight_failures(status, styles):
    assert trace.status_styles(status) == styles


def test_short_id_trims_uuid_unless_full():
    uuid = "cc772b50-c5e8-4c51-9aea-860944d84626"
    assert trace.short_id(uuid, False) == "cc772b50"
    assert trace.short_id(uuid, True) == uuid
    assert trace.short_id(None, False) == "-"


def test_rows_line_up_across_sources():
    """엣지 줄과 앱 ACCESS 줄의 상태·소요시간 열이 같은 자리에 와야 훑어볼 수 있다."""
    when = datetime(2026, 9, 28, 14, 2, 11, 412000, tzinfo=KST)
    edge = trace.format_edge(when, {"ts": 0, "status": 200, "duration": 0.423,
                                    "request": {"method": "GET", "uri": "/x", "client_ip": "10.0.0.0"}})
    app = trace.format_app(when, json.loads(app_line("2026-09-28T14:02:11.412+09:00")))
    assert edge.index("200") == app.index("200"), "상태 열이 같은 자리"
    # 오른쪽 정렬이므로 자리는 달라도 끝나는 열이 같아야 크기 비교가 된다
    assert edge.index("423ms") + len("423ms") == app.index("5ms") + len("5ms"), "소요시간 오른쪽 정렬"


def test_access_line_shows_short_id_and_full_id_flag():
    when = datetime(2026, 9, 28, 14, 0, tzinfo=KST)
    record = json.loads(app_line("2026-09-28T14:00:00+09:00", request_id="cc772b50-c5e8-4c51-9aea-860944d84626"))
    assert "rid=cc772b50 " in trace.format_app(when, record) + " "
    assert "rid=cc772b50-c5e8-4c51-9aea-860944d84626" in trace.format_app(when, record, full_id=True)


def test_continuation_lines_are_indented_under_the_body():
    when = datetime(2026, 9, 28, 14, 0, tzinfo=KST)
    out = trace.format_app(when, {"ts": "2026-09-28T14:00:00+09:00", "kind": "app", "level": "ERROR",
                                  "logger": "app.services.trips", "msg": "실패", "request_id": "r",
                                  "exc_type": "IntegrityError", "exc_message": "boom",
                                  "frames": ["app/services/trips.py:210:link_policy"]})
    body, cause, frame = out.split("\n")
    assert cause.startswith(trace.INDENT + "↳") and frame.startswith(trace.INDENT + "  ")
    assert len(trace.INDENT) == 19


# ----------------------------------------------------------------- 명령 짧게 (rev14)
def _args(argv):
    """main() 을 돌리지 않고 인자 해석 결과만 본다."""
    return trace.build_parser().parse_args(argv)


def test_dev_and_prod_are_short_forms_of_server():
    assert _args(["--dev", "--recent"]).server == "dev"
    assert _args(["--prod", "--recent"]).server == "prod"
    assert _args(["--server", "dev", "--recent"]).server == "dev"


def test_stats_is_an_alias_for_summary():
    assert _args(["--stats"]).summary is True
    assert _args(["--summary"]).summary is True


def test_server_defaults_to_none_so_env_can_decide():
    """옵션이 없으면 None - 호출부가 TRACE_SERVER 를 쓴다. 옵션이 있으면 옵션이 이긴다."""
    assert _args(["--recent"]).server is None
    assert _args(["--recent", "--server", "local"]).server == "local"


def test_wrapper_scripts_exist_and_pass_arguments():
    root = TRACE_PATH.parent
    bash_wrapper = (root / "trace").read_text(encoding="utf-8")
    cmd_wrapper = (root / "trace.cmd").read_text(encoding="ascii")
    assert '"$@"' in bash_wrapper and "trace.py" in bash_wrapper
    assert "%*" in cmd_wrapper and "trace.py" in cmd_wrapper
    # cmd 는 CRLF 가 아니면 REM 줄이 명령으로 샌다
    assert "\r\n" in (root / "trace.cmd").read_bytes().decode("ascii")


# ----------------------------------------------------------------- 재검토 보강
def _pep701_offenders(source: str) -> list[tuple[int, int]]:
    """f-string 안에서 바깥과 같은 따옴표를 다시 쓴 자리. 3.12 에서만 파싱되는 문법(PEP 701)이다.

    ast.parse(feature_version=(3, 11)) 로는 이 문법을 걸러내지 못한다(실측). 토큰으로 직접 본다.
    """
    import io
    import tokenize

    def delimiter(text: str) -> str:
        body = text.lstrip("rRfFbBuU")
        return body[:3] if body[:3] in ('"""', "'''") else body[:1]

    offenders, open_delims = [], []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        name = tokenize.tok_name[tok.type]
        if name in ("FSTRING_START", "STRING") and open_delims:
            if delimiter(tok.string).startswith(open_delims[-1]) and len(open_delims[-1]) == 1:
                offenders.append(tok.start)
        if name == "FSTRING_START":
            open_delims.append(delimiter(tok.string))
        elif name == "FSTRING_END":
            open_delims.pop()
    return offenders


@pytest.mark.skipif(not hasattr(__import__("tokenize"), "FSTRING_START"), reason="3.12 토크나이저가 필요하다")
def test_trace_script_stays_parseable_on_python_311():
    # 팀원 PC 는 버전이 제각각이다. 3.12 전용 문법이 섞이면 도구가 아예 뜨지 않는다.
    assert _pep701_offenders("x = f'{a if a else '':>5}'\n"), "검사기가 실제로 잡는지부터 확인"
    assert _pep701_offenders(TRACE_PATH.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("name", [
    "caddy-access-x'; rm -rf / #.log",
    "caddy-access-a b.log",
    'caddy-access-"x".log',
    "caddy-access-$(id).log",
])
def test_rotated_names_with_shell_characters_are_ignored(name, monkeypatch):
    """이름이 sh -c '…' 인용 안에 들어가므로 따옴표·공백·셸 문자가 섞인 이름은 받지 않는다."""
    monkeypatch.setattr(subprocess, "run", FakeDocker(listing={"c": ["caddy-access.log", name]}))
    files, _ = trace.list_rotated("c", "caddy-access", {})
    assert [Path(f).name for f in files] == ["caddy-access.log"]


# ----------------------------------------------------------------- 장기 보관본(--dir)
def test_archive_is_read_without_docker(tmp_path, monkeypatch):
    """scripts/pull_logs.py 가 빼 둔 달별 파일을 읽는다. docker 를 부르면 실패한다."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("--dir 은 서버에 접속하지 않는다"))
    (tmp_path / "backend-2026-09.log").write_bytes((app_line("2026-09-28T10:00:00+09:00") + "\n").encode())
    records = list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024))
    assert [r["ts"] for r in records] == ["2026-09-28T10:00:00+09:00"]
    assert list(trace.read_local_file("caddy-access", str(tmp_path), 1024)) == [], "아직 없는 스트림은 비어 있음"


def test_archive_reads_months_in_order_including_gzip(tmp_path):
    import gzip

    (tmp_path / "backend-2026-08.log.gz").write_bytes(
        gzip.compress((app_line("2026-08-10T10:00:00+09:00") + "\n").encode())
        + gzip.compress((app_line("2026-08-31T23:00:00+09:00") + "\n").encode())  # 늦게 붙은 멤버
    )
    (tmp_path / "backend-2026-08.log").write_bytes((app_line("2026-08-31T23:30:00+09:00") + "\n").encode())
    (tmp_path / "backend-2026-09.log").write_bytes((app_line("2026-09-01T09:00:00+09:00") + "\n").encode())
    (tmp_path / "backend-notes.txt").write_text("무시", "utf-8")
    records = list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024))
    assert [r["ts"][:16] for r in records] == ["2026-08-10T10:00", "2026-08-31T23:00", "2026-08-31T23:30", "2026-09-01T09:00"]


def test_archive_skips_months_before_since(tmp_path, capsys):
    (tmp_path / "backend-2026-07.log.gz").write_bytes(b"not gzip - opening this would fail")
    (tmp_path / "backend-2026-09.log").write_bytes((app_line("2026-09-28T10:00:00+09:00") + "\n").encode())
    cutoff = datetime(2026, 9, 1, tzinfo=KST)
    assert len(list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024, cutoff))) == 1
    assert "읽지 못해" not in capsys.readouterr().err, "--since 이전 달은 열지도 않는다"


def test_archive_over_the_cap_drops_the_cut_line(tmp_path, capsys):
    # 잘린 조각이 그 자체로 올바른 JSON 이 되게 만든다 - 버리지 않으면 가짜 레코드가 하나 더 나온다.
    tail_of_first = app_line("2026-09-28T09:00:00+09:00")
    first = "잘린앞부분" + tail_of_first
    second = app_line("2026-09-28T10:00:00+09:00")
    # 바이트로 쓴다 - Windows 의 write_text 는 \n 을 \r\n 으로 바꿔 자르는 위치가 어긋난다.
    (tmp_path / "backend-2026-09.log").write_bytes((first + "\n" + second + "\n").encode("utf-8"))
    cap = len((tail_of_first + "\n" + second + "\n").encode())
    records = list(trace.read_local_file("backend", str(tmp_path), cap))
    assert [r["ts"] for r in records] == ["2026-09-28T10:00:00+09:00"]
    assert "MB 만 읽었다" in capsys.readouterr().err


def test_dir_mode_end_to_end(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("--dir 은 서버에 접속하지 않는다"))
    (tmp_path / "backend-2026-09.log").write_bytes((app_line("2026-09-28T10:00:00+09:00") + "\n").encode())
    monkeypatch.setattr("sys.argv", ["trace", "--dir", str(tmp_path), "r1", "--since", "", "--color", "never"])
    assert trace.main() == 0
    assert "/api/x" in capsys.readouterr().out


def test_missing_key_prints_usage_instead_of_crashing(tmp_path, monkeypatch, capsys):
    # build_parser() 로 나눈 뒤 main() 이 없는 parser 를 불러 NameError 로 죽었다.
    monkeypatch.setattr("sys.argv", ["trace", "--dir", str(tmp_path)])
    with pytest.raises(SystemExit) as exit_info:
        trace.main()
    assert exit_info.value.code == 2
    assert "request_id 또는 user:<id> 가 필요하다" in capsys.readouterr().err


def test_dir_rejects_tail(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.argv", ["trace", "--dir", str(tmp_path), "--tail"])
    with pytest.raises(SystemExit):
        trace.main()


def test_archive_parts_are_read_in_number_order_before_the_plain_file(tmp_path):
    import gzip

    def line(ts):
        return (app_line(ts) + "\n").encode()

    # 해시는 무작위 순서가 되게 고른다 - 번호로만 정렬돼야 한다
    (tmp_path / "backend-2026-08.p99-000000000000.log.gz").write_bytes(gzip.compress(line("2026-08-20T10:00:00+09:00")))
    (tmp_path / "backend-2026-08.p01-ffffffffffff.log.gz").write_bytes(gzip.compress(line("2026-08-10T10:00:00+09:00")))
    (tmp_path / "backend-2026-08.p100-aaaaaaaaaaaa.log.gz").write_bytes(gzip.compress(line("2026-08-30T10:00:00+09:00")))
    (tmp_path / "backend-2026-08.log").write_bytes(line("2026-08-31T23:00:00+09:00"))
    records = list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024))
    assert [r["ts"][:10] for r in records] == ["2026-08-10", "2026-08-20", "2026-08-30", "2026-08-31"]


def test_archive_reads_only_the_newest_files_it_needs(tmp_path, capsys):
    """최근 파일부터 거꾸로 --max-mb 만큼만 읽는다. 오래된 달은 열지도 않는다."""
    (tmp_path / "backend-2026-07.p01-000000000000.log.gz").write_bytes(b"not gzip - opening this would warn")
    recent = (app_line("2026-09-28T10:00:00+09:00") + "\n").encode()
    (tmp_path / "backend-2026-09.log").write_bytes(recent * 3)
    records = list(trace.read_local_file("backend", str(tmp_path), len(recent) * 2))
    assert len(records) >= 1
    assert "읽지 못해" not in capsys.readouterr().err, "필요 없는 오래된 파일은 열지 않는다"


def test_a_broken_archive_file_is_skipped_with_a_notice(tmp_path, capsys):
    (tmp_path / "backend-2026-08.p01-000000000000.log.gz").write_bytes(b"not gzip")
    (tmp_path / "backend-2026-09.log").write_bytes((app_line("2026-09-28T10:00:00+09:00") + "\n").encode())
    records = list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024))
    assert len(records) == 1
    assert "읽지 못해 건너뛴다" in capsys.readouterr().err


def test_a_missing_archive_folder_is_an_error_not_empty(tmp_path):
    with pytest.raises(trace.LogReadError):
        list(trace.read_local_file("backend", str(tmp_path / "typo"), 1024))
